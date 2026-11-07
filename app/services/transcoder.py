import os
import subprocess


RENDITIONS = {
    360: {
        "bitrate": "800k",
        "maxrate": "856k",
        "bufsize": "1200k",
        "bandwidth": 900000,
    },
    720: {
        "bitrate": "2800k",
        "maxrate": "2996k",
        "bufsize": "4200k",
        "bandwidth": 3100000,
    },
    1080: {
        "bitrate": "5000k",
        "maxrate": "5350k",
        "bufsize": "7500k",
        "bandwidth": 5500000,
    },
}
def get_video_height(input_path: str) -> int:

    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=height",
            "-of", "csv=s=x:p=0",
            input_path,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )

    return int(result.stdout.strip())

def transcode_video(input_path: str, output_dir: str):

    source_height = get_video_height(input_path)

    os.makedirs(output_dir, exist_ok=True)

    generated_renditions = []

    # Only generate resolutions supported by the original video.
    resolutions = [
        height
        for height in RENDITIONS
        if height <= source_height
    ]

    # Handle videos smaller than 360p.
    if not resolutions:
        resolutions = [source_height - (source_height % 2)]

    for height in resolutions:

        if height <= 0:
            raise ValueError("Invalid video resolution")

        rendition_dir = os.path.join(
            output_dir,
            f"{height}p"
        )

        os.makedirs(rendition_dir, exist_ok=True)

        playlist_path = os.path.join(
            rendition_dir,
            "playlist.m3u8"
        )

        segment_pattern = os.path.join(
            rendition_dir,
            "segment_%05d.ts"
        )

        settings = RENDITIONS.get(
            height,
            {
                "bitrate": "400k",
                "maxrate": "428k",
                "bufsize": "600k",
                "bandwidth": 500000,
            }
        )

        command = [
            "ffmpeg",
            "-y",

            "-i", input_path,

            "-map", "0:v:0",
            "-map", "0:a:0?",

            "-vf", f"scale=-2:{height}",

            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",

            "-b:v", settings["bitrate"],
            "-maxrate", settings["maxrate"],
            "-bufsize", settings["bufsize"],

            "-c:a", "aac",
            "-b:a", "128k",

            "-force_key_frames", "expr:gte(t,n_forced*6)",
            "-sc_threshold", "0",

            "-f", "hls",
            "-hls_time", "6",
            "-hls_playlist_type", "vod",
            "-hls_flags", "independent_segments",

            "-hls_segment_filename", segment_pattern,

            playlist_path,
        ]

        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=6 * 60 * 60,
        )

        generated_renditions.append({
            "height": height,
            "bandwidth": settings["bandwidth"],
            "playlist": f"{height}p/playlist.m3u8",
        })

    return generated_renditions
    
def create_master_playlist(
    output_dir: str,
    renditions: list[dict]
):

    master_path = os.path.join(
        output_dir,
        "master.m3u8"
    )

    with open(master_path, "w") as file:

        file.write("#EXTM3U\n")
        file.write("#EXT-X-VERSION:3\n")

        for rendition in renditions:

            height = rendition["height"]
            bandwidth = rendition["bandwidth"]

            # Approximate width for a 16:9 video.
            width = round(height * 16 / 9)

            file.write(
                f"#EXT-X-STREAM-INF:"
                f"BANDWIDTH={bandwidth},"
                f"RESOLUTION={width}x{height}\n"
            )

            file.write(
                f"{rendition['playlist']}\n"
            )

    return master_path
    
    