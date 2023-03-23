"""Classes for voice assistant pipelines."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, Callable
from dataclasses import asdict, dataclass, field
import logging
from typing import Any

from homeassistant.backports.enum import StrEnum
from homeassistant.components import conversation, media_source, stt
from homeassistant.components.tts.media_source import (
    generate_media_source_id as tts_generate_media_source_id,
)
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.util.dt import utcnow

from .const import DOMAIN

DEFAULT_TIMEOUT = 30  # seconds

_LOGGER = logging.getLogger(__name__)


@callback
def async_get_pipeline(
    hass: HomeAssistant, pipeline_id: str | None = None, language: str | None = None
) -> Pipeline | None:
    """Get a pipeline by id or create one for a language."""
    if pipeline_id is not None:
        return hass.data[DOMAIN].get(pipeline_id)

    # Construct a pipeline for the required/configured language
    language = language or hass.config.language
    return Pipeline(
        name=language,
        language=language,
        stt_engine=None,  # first engine
        conversation_engine=None,  # first agent
        tts_engine=None,  # first engine
    )


class PipelineError(Exception):
    """Base class for pipeline errors."""

    def __init__(self, code: str, message: str) -> None:
        """Set error message."""
        self.code = code
        self.message = message

        super().__init__(f"Pipeline error code={code}, message={message}")


class SpeechToTextError(PipelineError):
    """Error in speech to text portion of pipeline."""


class IntentRecognitionError(PipelineError):
    """Error in intent recognition portion of pipeline."""


class TextToSpeechError(PipelineError):
    """Error in text to speech portion of pipeline."""


class PipelineEventType(StrEnum):
    """Event types emitted during a pipeline run."""

    RUN_START = "run-start"
    RUN_FINISH = "run-finish"
    STT_START = "stt-start"
    STT_FINISH = "stt-finish"
    INTENT_START = "intent-start"
    INTENT_FINISH = "intent-finish"
    TTS_START = "tts-start"
    TTS_FINISH = "tts-finish"
    ERROR = "error"


@dataclass
class PipelineEvent:
    """Events emitted during a pipeline run."""

    type: PipelineEventType
    data: dict[str, Any] | None = None
    timestamp: str = field(default_factory=lambda: utcnow().isoformat())

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the event."""
        return {
            "type": self.type,
            "timestamp": self.timestamp,
            "data": self.data or {},
        }


@dataclass
class Pipeline:
    """A voice assistant pipeline."""

    name: str
    language: str | None
    stt_engine: str | None
    conversation_engine: str | None
    tts_engine: str | None


class PipelineStage(StrEnum):
    """Stages of a pipeline."""

    STT = "stt"
    INTENT = "intent"
    TTS = "tts"


class PipelineRunValidationError(Exception):
    """Error when a pipeline run is not valid."""


class InvalidPipelineStagesError(PipelineRunValidationError):
    """Error when given an invalid combination of start/end stages."""

    def __init__(
        self,
        start_stage: PipelineStage,
        end_stage: PipelineStage,
    ) -> None:
        """Set error message."""
        super().__init__(
            f"Invalid stage combination: start={start_stage}, end={end_stage}"
        )


@dataclass
class PipelineRun:
    """Running context for a pipeline."""

    hass: HomeAssistant
    context: Context
    pipeline: Pipeline
    start_stage: PipelineStage
    end_stage: PipelineStage
    event_callback: Callable[[PipelineEvent], None]
    language: str = None  # type: ignore[assignment]

    def __post_init__(self):
        """Set language for pipeline."""
        self.language = self.pipeline.language or self.hass.config.language

        # stt -> intent -> tts
        if (self.start_stage, self.end_stage) in (
            (PipelineStage.INTENT, PipelineStage.STT),
            (PipelineStage.TTS, PipelineStage.STT),
            (PipelineStage.TTS, PipelineStage.INTENT),
        ):
            raise InvalidPipelineStagesError(self.start_stage, self.end_stage)

    def start(self):
        """Emit run start event."""
        self.event_callback(
            PipelineEvent(
                PipelineEventType.RUN_START,
                {
                    "pipeline": self.pipeline.name,
                    "language": self.language,
                },
            )
        )

    def finish(self):
        """Emit run finish event."""
        self.event_callback(
            PipelineEvent(
                PipelineEventType.RUN_FINISH,
            )
        )

    async def speech_to_text(
        self,
        metadata: stt.SpeechMetadata,
        stream: AsyncIterable[bytes],
        binary_handler_id: int,
    ) -> str:
        """Run speech to text portion of pipeline. Returns the spoken text."""
        engine = self.pipeline.stt_engine or "default"
        self.event_callback(
            PipelineEvent(
                PipelineEventType.STT_START,
                {
                    "engine": engine,
                    "metadata": asdict(metadata),
                    "handler_id": binary_handler_id,
                },
            )
        )

        try:
            # Load provider
            stt_provider = stt.async_get_provider(self.hass, self.pipeline.stt_engine)
            assert stt_provider is not None
        except Exception as src_error:
            stt_error = SpeechToTextError(
                code="stt-provider-missing",
                message=f"No speech to text provider for: {engine}",
            )
            _LOGGER.exception(stt_error.message)
            self.event_callback(
                PipelineEvent(
                    PipelineEventType.ERROR,
                    {"code": stt_error.code, "message": stt_error.message},
                )
            )
            raise stt_error from src_error

        try:
            # Transcribe audio stream
            result = await stt_provider.async_process_audio_stream(metadata, stream)
            assert (result.text is not None) and (
                result.result == stt.SpeechResultState.SUCCESS
            )
        except Exception as src_error:
            stt_error = SpeechToTextError(
                code="stt-stream-failed",
                message="Unexpected error during speech to text",
            )
            _LOGGER.exception(stt_error.message)
            self.event_callback(
                PipelineEvent(
                    PipelineEventType.ERROR,
                    {"code": stt_error.code, "message": stt_error.message},
                )
            )
            raise stt_error from src_error

        self.event_callback(
            PipelineEvent(
                PipelineEventType.STT_FINISH,
                {
                    "stt_output": {
                        "text": result.text,
                    }
                },
            )
        )

        return result.text

    async def recognize_intent(
        self, intent_input: str, conversation_id: str | None
    ) -> str:
        """Run intent recognition portion of pipeline. Returns text to speak."""
        self.event_callback(
            PipelineEvent(
                PipelineEventType.INTENT_START,
                {
                    "engine": self.pipeline.conversation_engine or "default",
                    "intent_input": intent_input,
                },
            )
        )

        try:
            conversation_result = await conversation.async_converse(
                hass=self.hass,
                text=intent_input,
                conversation_id=conversation_id,
                context=self.context,
                language=self.language,
                agent_id=self.pipeline.conversation_engine,
            )
        except Exception as src_error:
            intent_error = IntentRecognitionError(
                code="intent-failed",
                message="Unexpected error during intent recognition",
            )
            _LOGGER.exception(intent_error.message)
            self.event_callback(
                PipelineEvent(
                    PipelineEventType.ERROR,
                    {"code": intent_error.code, "message": intent_error.message},
                )
            )
            raise intent_error from src_error

        self.event_callback(
            PipelineEvent(
                PipelineEventType.INTENT_FINISH,
                {"intent_output": conversation_result.as_dict()},
            )
        )

        speech = conversation_result.response.speech.get("plain", {}).get("speech", "")

        return speech

    async def text_to_speech(self, tts_input: str) -> str:
        """Run text to speech portion of pipeline. Returns URL of TTS audio."""
        self.event_callback(
            PipelineEvent(
                PipelineEventType.TTS_START,
                {
                    "engine": self.pipeline.tts_engine or "default",
                    "tts_input": tts_input,
                },
            )
        )

        try:
            # Synthesize audio and get URL
            tts_media = await media_source.async_resolve_media(
                self.hass,
                tts_generate_media_source_id(
                    self.hass,
                    tts_input,
                    engine=self.pipeline.tts_engine,
                ),
            )
        except Exception as src_error:
            tts_error = TextToSpeechError(
                code="tts-failed",
                message="Unexpected error during text to speech",
            )
            _LOGGER.exception(tts_error.message)
            self.event_callback(
                PipelineEvent(
                    PipelineEventType.ERROR,
                    {"code": tts_error.code, "message": tts_error.message},
                )
            )
            raise tts_error from src_error

        self.event_callback(
            PipelineEvent(
                PipelineEventType.TTS_FINISH,
                {"tts_output": asdict(tts_media)},
            )
        )

        return tts_media.url


@dataclass
class PipelineInput:
    """Input to a pipeline run."""

    binary_handler_id: int | None = None
    """Id of binary websocket handler. Required when start_stage = stt."""

    stt_metadata: stt.SpeechMetadata | None = None
    """Metadata of stt input audio. Required when start_stage = stt."""

    stt_stream: AsyncIterable[bytes] | None = None
    """Input audio for stt. Required when start_stage = stt."""

    intent_input: str | None = None
    """Input for conversation agent. Required when start_stage = intent."""

    tts_input: str | None = None
    """Input for text to speech. Required when start_stage = tts."""

    conversation_id: str | None = None

    async def execute(
        self, run: PipelineRun, timeout: int | float | None = DEFAULT_TIMEOUT
    ):
        """Run pipeline with optional timeout."""
        await asyncio.wait_for(
            self._execute(run),
            timeout=timeout,
        )

    async def _execute(self, run: PipelineRun):
        self._validate(run.start_stage)

        # stt -> intent -> tts
        run.start()
        current_stage = run.start_stage

        # Speech to text
        intent_input = self.intent_input
        if current_stage == PipelineStage.STT:
            assert self.binary_handler_id is not None
            assert self.stt_metadata is not None
            assert self.stt_stream is not None
            intent_input = await run.speech_to_text(
                self.stt_metadata, self.stt_stream, self.binary_handler_id
            )
            current_stage = PipelineStage.INTENT

        if run.end_stage != PipelineStage.STT:
            tts_input = self.tts_input

            if current_stage == PipelineStage.INTENT:
                assert intent_input is not None
                tts_input = await run.recognize_intent(
                    intent_input, self.conversation_id
                )
                current_stage = PipelineStage.TTS

            if run.end_stage != PipelineStage.INTENT:
                if current_stage == PipelineStage.TTS:
                    assert tts_input is not None
                    await run.text_to_speech(tts_input)

        run.finish()

    def _validate(self, stage: PipelineStage):
        """Validate pipeline input against start stage."""
        if stage == PipelineStage.STT:
            if self.binary_handler_id is None:
                raise PipelineRunValidationError(
                    "binary_handler_id is required for speech to text"
                )

            if self.stt_metadata is None:
                raise PipelineRunValidationError(
                    "stt_metadata is required for speech to text"
                )

            if self.stt_stream is None:
                raise PipelineRunValidationError(
                    "stt_stream is required for speech to text"
                )
        elif stage == PipelineStage.INTENT:
            if self.intent_input is None:
                raise PipelineRunValidationError(
                    "intent_input is required for intent recognition"
                )
        elif stage == PipelineStage.TTS:
            if self.tts_input is None:
                raise PipelineRunValidationError(
                    "tts_input is required for text to speech"
                )
