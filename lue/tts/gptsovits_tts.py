"""GPT-SoVITS TTS backend for the Lue eBook reader."""

import asyncio
import logging
import os
import urllib.request
import urllib.parse
from rich.console import Console

from .base import TTSBase

# GPT-SoVITS API configuration
def _get_windows_host_ip() -> str:
    """Detect Windows host IP from WSL2 default gateway."""
    try:
        import subprocess
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True, text=True, timeout=3
        )
        for part in result.stdout.split():
            if part.count(".") == 3 and part != "default":
                return part
    except Exception:
        pass
    return "127.0.0.1"

GPTSOVITS_API_URL = os.environ.get("GPTSOVITS_URL", f"http://{_get_windows_host_ip()}:9880")
GPTSOVITS_REF_AUDIO = os.environ.get("GPTSOVITS_REF_AUDIO", "")
GPTSOVITS_PROMPT_TEXT = os.environ.get("GPTSOVITS_PROMPT_TEXT", "")
GPTSOVITS_PROMPT_LANG = os.environ.get("GPTSOVITS_PROMPT_LANG", "zh")


class GptSoVitsTTS(TTSBase):
    """TTS implementation using GPT-SoVITS local API server."""

    @property
    def name(self) -> str:
        return "gptsovits"

    @property
    def output_format(self) -> str:
        return "wav"

    def get_overlap_seconds(self) -> float:
        """Use a small overlap to avoid simultaneous playback of short sentences."""
        return 0.15

    def __init__(self, console: Console, voice: str = None, lang: str = None):
        super().__init__(console, voice, lang)
        self.api_url = GPTSOVITS_API_URL
        self.ref_audio = GPTSOVITS_REF_AUDIO
        self.prompt_text = GPTSOVITS_PROMPT_TEXT
        self.prompt_lang = GPTSOVITS_PROMPT_LANG
        self.text_lang = lang or "zh"

    async def initialize(self) -> bool:
        """Check if GPT-SoVITS API server is reachable."""
        if not self.ref_audio:
            self.console.print(
                "[bold red]GPTSOVITS_REF_AUDIO not set.[/bold red] "
                "Set it via environment variable or see docs/gptsovits/GPTSOVITS_SETUP.md"
            )
            return False
        if not self.prompt_text:
            self.console.print(
                "[bold red]GPTSOVITS_PROMPT_TEXT not set.[/bold red] "
                "Set it via environment variable or see docs/gptsovits/GPTSOVITS_SETUP.md"
            )
            return False
        try:
            req = urllib.request.urlopen(f"{self.api_url}/", timeout=3)
            req.close()
        except Exception:
            pass  # A 404/405 still means the server is up

        # Try a real connectivity check via the control endpoint
        try:
            urllib.request.urlopen(f"{self.api_url}/control", timeout=3)
        except urllib.error.HTTPError:
            # HTTP error means server responded — it's running
            self.initialized = True
            self.console.print("[green]GPT-SoVITS API is available.[/green]")
            return True
        except urllib.error.URLError as e:
            self.console.print(
                f"[bold red]GPT-SoVITS API not reachable at {self.api_url}[/bold red]"
            )
            self.console.print(
                "[yellow]Please start the API server first:[/yellow]"
            )
            self.console.print(
                r"[yellow]  cd E:\BaiduNetdiskDownload\GPT-SoVITS-v3lora-20250401[/yellow]"
            )
            self.console.print(
                r"[yellow]  runtime\python api_v2.py -a 127.0.0.1 -p 9880[/yellow]"
            )
            logging.error(f"GPT-SoVITS API connection failed: {e}")
            return False
        except Exception:
            pass

        self.initialized = True
        self.console.print("[green]GPT-SoVITS API is available.[/green]")
        return True

    async def generate_audio(self, text: str, output_path: str):
        """Call GPT-SoVITS API to synthesize speech and save to file."""
        if not self.initialized:
            raise RuntimeError("GPT-SoVITS TTS has not been initialized.")

        params = urllib.parse.urlencode({
            "text": text,
            "text_lang": self.text_lang,
            "ref_audio_path": self.ref_audio,
            "prompt_text": self.prompt_text,
            "prompt_lang": self.prompt_lang,
            "media_type": "wav",
            "streaming_mode": "false",
            "text_split_method": "cut5",
            "batch_size": 1,
            "speed_factor": 1.0,
            "sample_steps": 16,
        })

        url = f"{self.api_url}/tts?{params}"

        def _fetch() -> bytes:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return resp.read()

        try:
            audio_data = await asyncio.to_thread(_fetch)
            with open(output_path, "wb") as f:
                f.write(audio_data)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logging.error(
                f"GPT-SoVITS audio generation failed for text: '{text[:50]}...'",
                exc_info=True,
            )
            raise e

    async def warm_up(self):
        """Send a short test request to warm up the model."""
        if not self.initialized:
            return
        self.console.print("[bold cyan]Warming up GPT-SoVITS model...[/bold cyan]")
        import tempfile
        warmup_file = os.path.join(tempfile.gettempdir(), ".warmup_gptsovits.wav")
        try:
            await self.generate_audio("你好。", warmup_file)
            self.console.print("[green]GPT-SoVITS model is ready.[/green]")
        except Exception as e:
            self.console.print(
                "[bold yellow]Warning: GPT-SoVITS warm-up failed.[/bold yellow]"
            )
            logging.warning(f"GPT-SoVITS warm-up failed: {e}", exc_info=True)
        finally:
            if os.path.exists(warmup_file):
                try:
                    os.remove(warmup_file)
                except OSError:
                    pass
