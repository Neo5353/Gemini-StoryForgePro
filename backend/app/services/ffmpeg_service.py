"""FFmpeg Assembly Service — WALL-E's workshop for stitching beauty together.

Handles video assembly, transitions, title cards, subtitles,
music beds, and final encoding via subprocess calls to ffmpeg.
"""

import asyncio
import json
import logging
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("storyforge.ffmpeg")


class TransitionType(str, Enum):
    CUT = "cut"
    DISSOLVE = "dissolve"
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    CROSS_FADE = "cross_fade"


@dataclass
class SceneClip:
    """A video clip to include in the assembly."""
    path: str
    scene_id: str
    duration_seconds: float = 0.0
    transition_in: TransitionType = TransitionType.CUT
    transition_duration: float = 1.0  # seconds for dissolve/crossfade


class FFmpegError(Exception):
    """Raised when an ffmpeg command fails."""
    pass


class FFmpegService:
    """Video assembly and post-production via ffmpeg.

    WALL-E's workshop — carefully piecing together clips, adding
    transitions, music, and titles to create something beautiful.
    """

    # Default encoding settings
    DEFAULT_CRF = "18"  # High quality
    DEFAULT_PRESET = "slow"  # Better compression
    DEFAULT_CODEC = "libx264"
    DEFAULT_AUDIO_CODEC = "aac"
    DEFAULT_AUDIO_BITRATE = "192k"

    def __init__(self, work_dir: Optional[str] = None):
        """
        Args:
            work_dir: Temporary directory for intermediate files.
                      Created automatically if not specified.
        """
        self.work_dir = work_dir or tempfile.mkdtemp(prefix="storyforge_ffmpeg_")
        Path(self.work_dir).mkdir(parents=True, exist_ok=True)

    async def _run_ffmpeg(self, args: List[str], description: str = "") -> str:
        """Run an ffmpeg command and handle errors.

        Returns stdout on success, raises FFmpegError on failure.
        """
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning"] + args
        logger.info("FFmpeg [%s]: %s", description, " ".join(cmd))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace")
            logger.error("FFmpeg failed [%s]: %s", description, error_msg)
            raise FFmpegError(f"ffmpeg {description} failed: {error_msg}")

        if stderr:
            logger.debug("FFmpeg stderr [%s]: %s", description, stderr.decode()[:500])

        return stdout.decode("utf-8", errors="replace")

    async def _run_ffprobe(self, path: str) -> dict:
        """Run ffprobe to get media info."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return json.loads(stdout.decode()) if stdout else {}

    async def get_duration(self, path: str) -> float:
        """Get the duration of a media file in seconds."""
        info = await self._run_ffprobe(path)
        try:
            return float(info["format"]["duration"])
        except (KeyError, ValueError):
            return 0.0

    async def stitch_scenes(
        self,
        scene_clips: List[SceneClip],
        transitions: Optional[List[TransitionType]] = None,
        output_path: str = "",
    ) -> str:
        """Stitch multiple scene clips into a single video.

        Supports cut, dissolve, cross_fade, fade_in, fade_out transitions.

        Args:
            scene_clips: Ordered list of clips to stitch.
            transitions: Per-clip transition type (len = len(clips) - 1 for between-clip transitions).
                         If None, uses each clip's transition_in field.
            output_path: Destination path. Auto-generated if empty.

        Returns:
            Path to the stitched output video.
        """
        if not scene_clips:
            raise FFmpegError("No clips to stitch")

        if not output_path:
            output_path = os.path.join(
                self.work_dir, f"stitched_{uuid.uuid4().hex[:8]}.mp4"
            )

        # Single clip — just copy
        if len(scene_clips) == 1:
            clip = scene_clips[0]
            if clip.transition_in == TransitionType.FADE_IN:
                await self._run_ffmpeg(
                    ["-i", clip.path,
                     "-vf", f"fade=in:st=0:d={clip.transition_duration}",
                     "-c:v", self.DEFAULT_CODEC, "-c:a", "copy",
                     output_path],
                    "single clip with fade",
                )
            else:
                shutil.copy2(clip.path, output_path)
            return output_path

        # For complex transitions, we use the xfade filter
        all_cuts_only = all(
            (transitions[i] if transitions and i < len(transitions)
             else scene_clips[i + 1].transition_in) == TransitionType.CUT
            for i in range(len(scene_clips) - 1)
        )

        if all_cuts_only:
            return await self._stitch_concat(scene_clips, output_path)
        else:
            return await self._stitch_with_transitions(
                scene_clips, transitions, output_path
            )

    async def _stitch_concat(
        self, clips: List[SceneClip], output_path: str
    ) -> str:
        """Simple concatenation using ffmpeg concat demuxer."""
        # First normalize all clips to same resolution/framerate
        normalized = await self._normalize_clips(clips)

        concat_file = os.path.join(self.work_dir, f"concat_{uuid.uuid4().hex[:6]}.txt")
        with open(concat_file, "w") as f:
            for path in normalized:
                f.write(f"file '{path}'\n")

        await self._run_ffmpeg(
            ["-f", "concat", "-safe", "0", "-i", concat_file,
             "-c:v", self.DEFAULT_CODEC, "-crf", self.DEFAULT_CRF,
             "-c:a", self.DEFAULT_AUDIO_CODEC, "-b:a", self.DEFAULT_AUDIO_BITRATE,
             output_path],
            "concat stitch",
        )
        return output_path

    async def _normalize_clips(self, clips: List[SceneClip]) -> List[str]:
        """Normalize clips to consistent resolution and frame rate."""
        normalized = []
        for i, clip in enumerate(clips):
            out = os.path.join(
                self.work_dir, f"norm_{i}_{uuid.uuid4().hex[:6]}.mp4"
            )
            await self._run_ffmpeg(
                ["-i", clip.path,
                 "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
                        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30",
                 "-c:v", self.DEFAULT_CODEC, "-crf", self.DEFAULT_CRF,
                 "-c:a", self.DEFAULT_AUDIO_CODEC, "-b:a", self.DEFAULT_AUDIO_BITRATE,
                 "-ar", "48000", "-ac", "2",
                 out],
                f"normalize clip {i}",
            )
            normalized.append(out)
        return normalized

    async def _stitch_with_transitions(
        self,
        clips: List[SceneClip],
        transitions: Optional[List[TransitionType]],
        output_path: str,
    ) -> str:
        """Stitch clips with xfade transitions between them."""
        # Normalize first
        normalized = await self._normalize_clips(clips)

        # Build xfade filter chain
        # xfade works on pairs: [0] xfade [1] -> [tmp1] xfade [2] -> ...
        filter_parts = []
        current_input = "[0:v]"
        current_offset = 0.0

        for i in range(len(normalized) - 1):
            clip = clips[i]
            duration = clip.duration_seconds or await self.get_duration(normalized[i])
            trans = (
                transitions[i]
                if transitions and i < len(transitions)
                else clips[i + 1].transition_in
            )
            trans_dur = clips[i + 1].transition_duration

            # Compute offset (when the transition starts)
            offset = current_offset + duration - trans_dur
            if offset < 0:
                offset = current_offset + duration * 0.8  # fallback

            xfade_type = self._map_transition(trans)
            next_input = f"[{i + 1}:v]"
            out_label = f"[v{i}]" if i < len(normalized) - 2 else "[vout]"

            filter_parts.append(
                f"{current_input}{next_input}xfade=transition={xfade_type}"
                f":duration={trans_dur}:offset={offset}{out_label}"
            )
            current_input = out_label
            current_offset = offset

        # Audio: simple concat (crossfade audio too for smoothness)
        audio_parts = []
        for i in range(len(normalized)):
            audio_parts.append(f"[{i}:a]")
        audio_filter = "".join(audio_parts) + f"concat=n={len(normalized)}:v=0:a=1[aout]"

        filter_complex = ";".join(filter_parts) + ";" + audio_filter

        input_args = []
        for path in normalized:
            input_args.extend(["-i", path])

        await self._run_ffmpeg(
            input_args + [
                "-filter_complex", filter_complex,
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", self.DEFAULT_CODEC, "-crf", self.DEFAULT_CRF,
                "-c:a", self.DEFAULT_AUDIO_CODEC, "-b:a", self.DEFAULT_AUDIO_BITRATE,
                output_path,
            ],
            "xfade stitch",
        )
        return output_path

    @staticmethod
    def _map_transition(trans: TransitionType) -> str:
        """Map our transition types to ffmpeg xfade transition names."""
        mapping = {
            TransitionType.CUT: "fade",  # shortest possible fade
            TransitionType.DISSOLVE: "dissolve",
            TransitionType.FADE_IN: "fade",
            TransitionType.FADE_OUT: "fade",
            TransitionType.CROSS_FADE: "fade",
        }
        return mapping.get(trans, "fade")

    async def add_music_bed(
        self,
        video_path: str,
        music_path: str,
        output_path: str = "",
        music_volume: float = 0.15,
        fade_out_seconds: float = 3.0,
    ) -> str:
        """Mix a music track under the video's existing audio.

        Args:
            video_path: Input video with dialogue/SFX audio.
            music_path: Background music track.
            output_path: Destination. Auto-generated if empty.
            music_volume: Music volume relative to original (0.0-1.0).
            fade_out_seconds: Fade out music at the end.
        """
        if not output_path:
            output_path = os.path.join(
                self.work_dir, f"music_{uuid.uuid4().hex[:8]}.mp4"
            )

        video_duration = await self.get_duration(video_path)
        fade_start = max(0, video_duration - fade_out_seconds)

        # Mix: original audio + music bed at reduced volume with fade out
        filter_complex = (
            f"[1:a]volume={music_volume},"
            f"afade=t=out:st={fade_start}:d={fade_out_seconds}[music];"
            f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )

        await self._run_ffmpeg(
            ["-i", video_path, "-i", music_path,
             "-filter_complex", filter_complex,
             "-map", "0:v", "-map", "[aout]",
             "-c:v", "copy",
             "-c:a", self.DEFAULT_AUDIO_CODEC, "-b:a", self.DEFAULT_AUDIO_BITRATE,
             "-shortest",
             output_path],
            "add music bed",
        )
        return output_path

    async def add_title_card(
        self,
        video_path: str,
        title: str,
        subtitle: str = "",
        output_path: str = "",
        duration: float = 4.0,
        bg_color: str = "black",
        font_color: str = "white",
        font_size: int = 72,
        position: str = "start",
    ) -> str:
        """Add a title card (text on solid background) before or after the video.

        Args:
            video_path: Input video.
            title: Main title text.
            subtitle: Subtitle text (smaller, below title).
            output_path: Destination.
            duration: Title card duration in seconds.
            bg_color: Background color.
            font_color: Text color.
            font_size: Title font size.
            position: "start" or "end".
        """
        if not output_path:
            output_path = os.path.join(
                self.work_dir, f"titled_{uuid.uuid4().hex[:8]}.mp4"
            )

        # Create title card video
        title_path = os.path.join(
            self.work_dir, f"titlecard_{uuid.uuid4().hex[:6]}.mp4"
        )

        # Escape special characters for drawtext
        safe_title = title.replace("'", "\\'").replace(":", "\\:")
        safe_subtitle = subtitle.replace("'", "\\'").replace(":", "\\:")

        drawtext = (
            f"drawtext=text='{safe_title}':fontsize={font_size}:"
            f"fontcolor={font_color}:x=(w-text_w)/2:y=(h-text_h)/2-40"
        )
        if subtitle:
            drawtext += (
                f",drawtext=text='{safe_subtitle}':fontsize={font_size // 2}:"
                f"fontcolor={font_color}@0.8:x=(w-text_w)/2:y=(h/2)+40"
            )

        # Generate title card
        await self._run_ffmpeg(
            ["-f", "lavfi",
             "-i", f"color=c={bg_color}:s=1920x1080:d={duration}:r=30",
             "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={duration}",
             "-vf", drawtext,
             "-c:v", self.DEFAULT_CODEC, "-crf", self.DEFAULT_CRF,
             "-c:a", self.DEFAULT_AUDIO_CODEC,
             "-shortest",
             title_path],
            "generate title card",
        )

        # Concatenate with video
        concat_file = os.path.join(
            self.work_dir, f"title_concat_{uuid.uuid4().hex[:6]}.txt"
        )
        if position == "start":
            order = [title_path, video_path]
        else:
            order = [video_path, title_path]

        with open(concat_file, "w") as f:
            for p in order:
                f.write(f"file '{p}'\n")

        # Need to normalize the video first to match title card specs
        norm_video = os.path.join(
            self.work_dir, f"norm_for_title_{uuid.uuid4().hex[:6]}.mp4"
        )
        await self._run_ffmpeg(
            ["-i", video_path,
             "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
                    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30",
             "-c:v", self.DEFAULT_CODEC, "-crf", self.DEFAULT_CRF,
             "-c:a", self.DEFAULT_AUDIO_CODEC, "-ar", "48000", "-ac", "2",
             norm_video],
            "normalize for title concat",
        )

        with open(concat_file, "w") as f:
            if position == "start":
                f.write(f"file '{title_path}'\n")
                f.write(f"file '{norm_video}'\n")
            else:
                f.write(f"file '{norm_video}'\n")
                f.write(f"file '{title_path}'\n")

        await self._run_ffmpeg(
            ["-f", "concat", "-safe", "0", "-i", concat_file,
             "-c:v", self.DEFAULT_CODEC, "-crf", self.DEFAULT_CRF,
             "-c:a", self.DEFAULT_AUDIO_CODEC,
             output_path],
            "concat title card",
        )
        return output_path

    async def add_subtitles(
        self,
        video_path: str,
        subtitle_track: str,
        output_path: str = "",
        burn_in: bool = True,
    ) -> str:
        """Add subtitles to a video.

        Args:
            video_path: Input video.
            subtitle_track: Path to .srt or .ass subtitle file.
            output_path: Destination.
            burn_in: If True, burn subtitles into video. If False, add as stream.
        """
        if not output_path:
            output_path = os.path.join(
                self.work_dir, f"subbed_{uuid.uuid4().hex[:8]}.mp4"
            )

        if burn_in:
            # Burn in — hardcode into video frames
            # Escape path for subtitles filter
            safe_sub = subtitle_track.replace("'", "\\'").replace(":", "\\:")
            await self._run_ffmpeg(
                ["-i", video_path,
                 "-vf", f"subtitles='{safe_sub}'",
                 "-c:v", self.DEFAULT_CODEC, "-crf", self.DEFAULT_CRF,
                 "-c:a", "copy",
                 output_path],
                "burn-in subtitles",
            )
        else:
            # Soft subtitles — add as separate stream
            await self._run_ffmpeg(
                ["-i", video_path, "-i", subtitle_track,
                 "-c:v", "copy", "-c:a", "copy",
                 "-c:s", "mov_text",
                 output_path],
                "soft subtitles",
            )

        return output_path

    async def encode_final(
        self,
        video_path: str,
        resolution: str = "1080p",
        output_path: str = "",
        codec: str = "libx264",
        crf: str = "18",
        preset: str = "slow",
    ) -> str:
        """Final encode pass with target resolution and quality.

        Args:
            video_path: Input video.
            resolution: Target resolution (720p, 1080p, 4k).
            output_path: Destination.
            codec: Video codec.
            crf: Constant Rate Factor (lower = higher quality).
            preset: Encoding speed preset.
        """
        if not output_path:
            output_path = os.path.join(
                self.work_dir, f"final_{uuid.uuid4().hex[:8]}.mp4"
            )

        res_map = {
            "720p": "1280:720",
            "1080p": "1920:1080",
            "4k": "3840:2160",
        }
        scale = res_map.get(resolution, "1920:1080")

        await self._run_ffmpeg(
            ["-i", video_path,
             "-vf", f"scale={scale}:force_original_aspect_ratio=decrease,"
                    f"pad={scale.replace(':', ':')}:(ow-iw)/2:(oh-ih)/2",
             "-c:v", codec, "-crf", crf, "-preset", preset,
             "-c:a", self.DEFAULT_AUDIO_CODEC, "-b:a", self.DEFAULT_AUDIO_BITRATE,
             "-movflags", "+faststart",  # Web-optimized MP4
             output_path],
            f"final encode {resolution}",
        )
        return output_path

    async def extract_last_frame(
        self, video_path: str, output_path: str = ""
    ) -> str:
        """Extract the last frame of a video as an image.

        Used for scene continuity — last frame of scene N = first frame of scene N+1.
        """
        if not output_path:
            output_path = os.path.join(
                self.work_dir, f"lastframe_{uuid.uuid4().hex[:8]}.png"
            )

        # Get duration first
        duration = await self.get_duration(video_path)
        seek_time = max(0, duration - 0.1)

        await self._run_ffmpeg(
            ["-ss", str(seek_time), "-i", video_path,
             "-vframes", "1", "-q:v", "2",
             output_path],
            "extract last frame",
        )
        return output_path

    def cleanup(self):
        """Remove temporary working directory."""
        if self.work_dir and Path(self.work_dir).exists():
            shutil.rmtree(self.work_dir, ignore_errors=True)
            logger.info("Cleaned up work dir: %s", self.work_dir)
