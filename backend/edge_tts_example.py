#!/usr/bin/env python3

"""Sync variant of the async .stream() method to
get audio chunks and feed them to SubMaker to
generate subtitles"""

import edge_tts

TEXT = "早晨！食咗未呀？"
VOICE = "zh-HK-WanLungNeural"
OUTPUT_FILE = "test.mp3"
SRT_FILE = "test.srt"


def main() -> None:
    """Main function"""
    communicate = edge_tts.Communicate(TEXT, VOICE)
    submaker = edge_tts.SubMaker()
    with open(OUTPUT_FILE, "wb") as file:
        for chunk in communicate.stream_sync():
            if chunk["type"] == "audio":
                file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)

    with open(SRT_FILE, "w", encoding="utf-8") as file:
        file.write(submaker.get_srt())


if __name__ == "__main__":
    main()
