"""Static file handling for HTTP component."""
import logging
from pathlib import Path

from aiohttp import hdrs
from aiohttp.web import FileResponse
from aiohttp.web_exceptions import (
    HTTPForbidden,
    HTTPNotFound,
    HTTPUnauthorized,
)
from aiohttp.web_urldispatcher import StaticResource

from .const import KEY_AUTHENTICATED, KEY_REAL_IP
from .ban import process_success_login

CACHE_TIME = 31 * 86400  # = 1 month
CACHE_HEADERS = {hdrs.CACHE_CONTROL: "public, max-age={}".format(CACHE_TIME)}

_LOGGER = logging.getLogger(__name__)


# https://github.com/PyCQA/astroid/issues/633
# pylint: disable=duplicate-bases
class CachingStaticResource(StaticResource):
    """Static Resource handler that will add cache headers."""

    async def _handle(self, request):
        """Handle HTTP request."""
        rel_url = request.match_info['filename']
        try:
            filename = Path(rel_url)
            if filename.anchor:
                # rel_url is an absolute name like
                # /static/\\machine_name\c$ or /static/D:\path
                # where the static dir is totally different
                raise HTTPForbidden()
            filepath = self._directory.joinpath(filename).resolve()
            if not self._follow_symlinks:
                filepath.relative_to(self._directory)
        except (ValueError, FileNotFoundError) as error:
            # relatively safe
            raise HTTPNotFound() from error
        except Exception as error:
            # perm error or other kind!
            request.app.logger.exception(error)
            raise HTTPNotFound() from error

        # on opening a dir, load its contents if allowed
        if filepath.is_dir():
            return await super()._handle(request)
        if filepath.is_file():
            return FileResponse(
                filepath, chunk_size=self._chunk_size, headers=CACHE_HEADERS)
        raise HTTPNotFound


class SecureStaticResource(StaticResource):
    """Static Resource handler that will require authorize."""

    async def _handle(self, request):
        """Handle HTTP request."""
        authenticated = request.get(KEY_AUTHENTICATED, False)
        if authenticated:
            await process_success_login(request)
        else:
            raise HTTPUnauthorized()

        _LOGGER.info('Serving %s to %s (auth: %s)',
                     request.path, request.get(KEY_REAL_IP), authenticated)

        return await super()._handle(request)
