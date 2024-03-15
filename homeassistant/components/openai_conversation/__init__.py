"""The OpenAI Conversation integration."""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
from typing import Literal

import openai
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, MATCH_ALL
from homeassistant.core import (
    Context,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    TemplateError,
)
from homeassistant.helpers import (
    config_validation as cv,
    intent,
    issue_registry as ir,
    selector,
    template,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import ulid

from .const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DEFAULT_CHAT_MODEL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_PROMPT,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
SERVICE_GENERATE_IMAGE = "generate_image"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up OpenAI Conversation."""

    async def render_image(call: ServiceCall) -> ServiceResponse:
        """Render an image with dall-e."""
        client = hass.data[DOMAIN][call.data["config_entry"]]

        if call.data["size"] in ("256", "512", "1024"):
            ir.async_create_issue(
                hass,
                DOMAIN,
                "image_size_deprecated_format",
                breaks_in_ha_version="2024.7.0",
                is_fixable=False,
                is_persistent=True,
                learn_more_url="https://www.home-assistant.io/integrations/openai_conversation/",
                severity=ir.IssueSeverity.WARNING,
                translation_key="image_size_deprecated_format",
            )
            size = "1024x1024"
        else:
            size = call.data["size"]

        try:
            response = await client.images.generate(
                model="dall-e-3",
                prompt=call.data["prompt"],
                size=size,
                quality=call.data["quality"],
                style=call.data["style"],
                response_format="url",
                n=1,
            )
        except openai.OpenAIError as err:
            raise HomeAssistantError(f"Error generating image: {err}") from err

        return response.data[0].model_dump(exclude={"b64_json"})

    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_IMAGE,
        render_image,
        schema=vol.Schema(
            {
                vol.Required("config_entry"): selector.ConfigEntrySelector(
                    {
                        "integration": DOMAIN,
                    }
                ),
                vol.Required("prompt"): cv.string,
                vol.Optional("size", default="1024x1024"): vol.In(
                    ("1024x1024", "1024x1792", "1792x1024", "256", "512", "1024")
                ),
                vol.Optional("quality", default="standard"): vol.In(("standard", "hd")),
                vol.Optional("style", default="vivid"): vol.In(("vivid", "natural")),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenAI Conversation from a config entry."""
    client = openai.AsyncOpenAI(api_key=entry.data[CONF_API_KEY])
    try:
        await hass.async_add_executor_job(client.with_options(timeout=10.0).models.list)
    except openai.AuthenticationError as err:
        _LOGGER.error("Invalid API key: %s", err)
        return False
    except openai.OpenAIError as err:
        raise ConfigEntryNotReady(err) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client

    conversation.async_set_agent(hass, entry, OpenAIAgent(hass, entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload OpenAI."""
    hass.data[DOMAIN].pop(entry.entry_id)
    conversation.async_unset_agent(hass, entry)
    return True


class OpenAIAgent(conversation.AbstractConversationAgent):
    """OpenAI conversation agent."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry
        self.history: dict[str, list[dict]] = {}
        self.tools: list[tuple[dict, Callable]] = []

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    def register_tool(self, specification: dict, async_callback: Callable) -> None:
        """Register a function that the assistant may execute."""
        if specification["function"]["name"] in [
            tool[0]["function"]["name"] for tool in self.tools
        ]:
            raise RuntimeError(
                f"Function {specification['function']['name']} already registered"
            )

        self.tools.append((specification, async_callback))

    def unregister_tool(self, function_name: str) -> None:
        """Remove the function from the list of available tools for the assistant."""
        self.tools = [
            tool for tool in self.tools if tool[0]["function"]["name"] != function_name
        ]

    async def async_call_tool(
        self, context: Context, tool_name: str, tool_args: str
    ) -> str:
        """Wrap the function call to parse the arguments and handle exceptions."""
        available_tools = {tool["function"]["name"]: func for tool, func in self.tools}

        _LOGGER.debug("Function call: %s(%s)", tool_name, tool_args)

        try:
            function_to_call = available_tools[tool_name]
            parsed_args = json.loads(tool_args)
            response = await function_to_call(self.hass, context, **parsed_args)
            response_str = json.dumps(response)

        except Exception as e:  # pylint: disable=broad-exception-caught
            response = {"error": type(e).__name__}
            if str(e):
                response["error_text"] = str(e)
            response_str = json.dumps(response)

        _LOGGER.debug("Function response: %s", response_str)

        return response_str

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        raw_prompt = self.entry.options.get(CONF_PROMPT, DEFAULT_PROMPT)
        model = self.entry.options.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL)
        max_tokens = self.entry.options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS)
        top_p = self.entry.options.get(CONF_TOP_P, DEFAULT_TOP_P)
        temperature = self.entry.options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE)

        if user_input.conversation_id in self.history:
            conversation_id = user_input.conversation_id
            messages = self.history[conversation_id]
        else:
            conversation_id = ulid.ulid_now()
            try:
                prompt = self._async_generate_prompt(
                    raw_prompt, user_input.device_id, user_input.context.user_id
                )
            except TemplateError as err:
                _LOGGER.error("Error rendering prompt: %s", err)
                intent_response = intent.IntentResponse(language=user_input.language)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    f"Sorry, I had a problem with my template: {err}",
                )
                return conversation.ConversationResult(
                    response=intent_response, conversation_id=conversation_id
                )
            messages = [{"role": "system", "content": prompt}]

        messages.append({"role": "user", "content": user_input.text})

        _LOGGER.debug("Prompt for %s: %s", model, messages)

        client = self.hass.data[DOMAIN][self.entry.entry_id]

        tool_calls = True
        while tool_calls:
            try:
                result = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=[x[0] for x in self.tools],
                    max_tokens=max_tokens,
                    top_p=top_p,
                    temperature=temperature,
                    user=conversation_id,
                )
            except openai.OpenAIError as err:
                intent_response = intent.IntentResponse(language=user_input.language)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    f"Sorry, I had a problem talking to OpenAI: {err}",
                )
                return conversation.ConversationResult(
                    response=intent_response, conversation_id=conversation_id
                )

            _LOGGER.debug("Response %s", result)
            response = result.choices[0].message
            messages.append(response)
            tool_calls = response.tool_calls

            if tool_calls:
                for tool_call in tool_calls:  # type: ignore[attr-defined]
                    function_response = await self.async_call_tool(
                        user_input.context,
                        tool_call.function.name,
                        tool_call.function.arguments,
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.function.name,
                            "content": function_response,
                        }
                    )

        self.history[conversation_id] = messages

        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(response.content)
        return conversation.ConversationResult(
            response=intent_response, conversation_id=conversation_id
        )

    def _async_generate_prompt(
        self, raw_prompt: str, device_id: str | None, user_id: str | None
    ) -> str:
        """Generate a prompt for the user."""
        return template.Template(raw_prompt, self.hass).async_render(
            {
                "ha_name": self.hass.config.location_name,
                "device_id": device_id,
                "user_id": user_id,
            },
            parse_result=False,
        )


@callback
async def async_register_tool(
    hass: HomeAssistant, agent_id: str, specification: dict, async_callback: Callable
) -> None:
    """Register a function that the assistant may execute."""
    agent = await conversation._get_agent_manager(hass).async_get_agent(agent_id)  # pylint: disable=protected-access
    if not isinstance(agent, OpenAIAgent):
        raise TypeError("Agent ID must correspond to openai_conversation agent")
    agent.register_tool(specification, async_callback)


@callback
async def async_unregister_tool(
    hass: HomeAssistant, agent_id: str, function_name: str
) -> None:
    """Remove the function from the list of available tools for the assistant."""
    agent = await conversation._get_agent_manager(hass).async_get_agent(agent_id)  # pylint: disable=protected-access
    if not isinstance(agent, OpenAIAgent):
        raise TypeError("Agent ID must correspond to openai_conversation agent")
    agent.unregister_tool(function_name)
