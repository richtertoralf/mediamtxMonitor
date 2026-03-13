#!/bin/sh

# /usr/local/bin/yt-push.sh 

set -eu

KEYFILE="/usr/local/etc/youtube_keys.map"

if [ ! -f "$KEYFILE" ]; then
  echo "Key file not found: $KEYFILE" >&2
  exit 1
fi

if [ -z "${MTX_PATH:-}" ]; then
  echo "MTX_PATH is not set" >&2
  exit 1
fi

KEY="$(
  awk -F= -v path="$MTX_PATH" '
    $1 == path {
      print substr($0, index($0, "=") + 1)
      found=1
      exit
    }
    END {
      if (!found) exit 1
    }
  ' "$KEYFILE"
)" || {
  echo "No YouTube key found for path: $MTX_PATH" >&2
  exit 1
}

exec ffmpeg \
  -loglevel warning \
  -rtsp_transport tcp \
  -i "rtsp://127.0.0.1:${RTSP_PORT}/${MTX_PATH}" \
  -c copy \
  -f flv \
  "rtmp://a.rtmp.youtube.com/live2/${KEY}"