# pylint: disable=missing-docstring
# flake8: noqa: E501
import asyncio
import argparse
import websockets
import os
import sys
import re
import telnetlib
import subprocess
import time
import random
import signal

# Try to import configuration from config.py if it exists
try:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from config import CLIENT_TYPE, AUTH_TOKEN, SERVER_URL, VLC_PORT, VIDEO_PATH, VLC_ADVERTISE_HOST, VLC_CONNECT_HOST
    DEFAULT_CLIENT_TYPE = CLIENT_TYPE
    DEFAULT_AUTH_TOKEN = AUTH_TOKEN
    DEFAULT_SERVER_URL = SERVER_URL
    DEFAULT_VLC_ADVERTISE_HOST = VLC_ADVERTISE_HOST
    DEFAULT_VLC_CONNECT_HOST = VLC_CONNECT_HOST
    DEFAULT_VLC_PORT = VLC_PORT
    DEFAULT_VIDEO_PATH = VIDEO_PATH
except ImportError:
    # Fallback to defaults if config.py doesn't exist
    DEFAULT_CLIENT_TYPE = "seeker"
    DEFAULT_AUTH_TOKEN = "secret_token_123"
    DEFAULT_SERVER_URL = "ws://localhost:8765"
    DEFAULT_VLC_ADVERTISE_HOST = "localhost"
    DEFAULT_VLC_CONNECT_HOST = "localhost"
    DEFAULT_VLC_PORT = 4212
    DEFAULT_VIDEO_PATH = "/path/to/video.mp4"

VLC_PROCESS = None


def send_command_to_vlc(command, host, port):
    """Sends a command to VLC and returns the response."""
    try:
        with telnetlib.Telnet(host, port) as tn:
            tn.read_until(b">", timeout=1)
            tn.write(command.encode("utf-8") + b"\n")
            # response = tn.read_until(b">", timeout=1).decode("utf-8").strip()
            response = tn.read_eager().decode("utf-8").strip()
            print(f"VLC command {command} response: {response}")
            return response
    except Exception as e:
        print(f"Error sending command to VLC: {e}")
        return None


def start_vlc(video_path, host, port):
    """Start VLC with the specified video and return the process."""
    # Launch VLC with loop mode enabled
    vlc_command = [
        "cvlc", video_path,
        "--intf", "rc",
        "--rc-host", f"{host}:{port}",
        "--loop",  # Makes the video restart automatically after it ends
        "--no-video-title-show",
        "--fullscreen",  # Run in fullscreen mode
        "--metadata-network-access",  # Allow VLC to access metadata from the network to get the video duration
    ]

    print(f"Starting VLC with video: {video_path}")
    vlc_process = subprocess.Popen(vlc_command)
    time.sleep(2)  # Give VLC some time to start

    return vlc_process


def get_video_duration(host, port):
    """Get the duration of the currently playing video in seconds."""
    try:
        response = send_command_to_vlc("get_length", host, port)
        if response and response.isdigit():
            return int(response)
        return 0
    except Exception:
        return 0


def parse_timecode(timecode):
    """Convert timecode format (hh:mm:ss, mm:ss or ss, xx% or -1) to seconds, supporting percentages and -1 for random."""
    # Match hh:mm:ss format
    match = re.match(r'^(\d+):(\d+):(\d+)$', timecode)
    if match:
        hours, minutes, seconds = map(int, match.groups())
        total_seconds = hours * 3600 + minutes * 60 + seconds
        return total_seconds

    # Match mm:ss format
    match = re.match(r'^(\d+):(\d+)$', timecode)
    if match:
        minutes, seconds = map(int, match.groups())
        total_seconds = minutes * 60 + seconds
        return total_seconds

    # Match ss format
    if re.match(r'^\d+$', timecode):
        return int(timecode)

    # Match xx% format
    match = re.match(r'^(\d+)%$', timecode)
    if match:
        percentage = int(match.group(1))
        total_duration = get_video_duration(DEFAULT_VLC_CONNECT_HOST, DEFAULT_VLC_PORT)
        return int(percentage * 0.01 * total_duration)

    # Match -1 for random
    if timecode == "-1":
        total_duration = get_video_duration(DEFAULT_VLC_CONNECT_HOST, DEFAULT_VLC_PORT)
        return random.randint(0, total_duration)

    return None

async def connect_to_server(client_type, auth_token, server_url):
    try:
        async with websockets.connect(server_url) as websocket:
            print(f"Connected to WebSocket server as {client_type}")

            # Send auth token and client type as first message
            await websocket.send(f"{auth_token}:{client_type}")
            print("Sent authentication token and client type")

            # Receive and print messages from the server
            while True:
                try:
                    message = await websocket.recv()
                    print(f"Received from server: {message}")

                    # Process specific commands
                    if message.startswith("/seek ") and client_type == "seeker":
                        # Extract timecode from message (format: /seek hh:mm:ss or /seek mm:ss or /seek ss or /seek xx% or /seek -1)
                        timecode = message[6:].strip()
                        seconds = parse_timecode(timecode)
                        total_duration = get_video_duration(DEFAULT_VLC_CONNECT_HOST, DEFAULT_VLC_PORT)

                        if seconds is not None:
                            print(
                                f"⚠️ SEEK COMMAND RECEIVED - Seeking to {timecode} ({seconds} seconds)")
                            response = send_command_to_vlc(
                                f"seek {seconds}", DEFAULT_VLC_CONNECT_HOST, DEFAULT_VLC_PORT)
                            await websocket.send(f"seeked {seconds} of {total_duration}")
                            print(f"VLC response: {response}")
                        else:
                            print(f"⚠️ Invalid timecode format: {timecode}")
                            # Could send error back to server here

                    elif message == "/switch" and client_type == "switcher":
                        print("🔄 SWITCH COMMAND RECEIVED - ACTIVATING SWITCHER MODE")
                        # Add switcher-specific logic here

                except websockets.exceptions.ConnectionClosed:
                    print("Connection closed by server")
                    break
                except Exception as e:
                    print(f"Error receiving message: {e}")
                    break

    except Exception as e:
        print(f"Failed to connect to server: {e}")
        # Wait before reconnecting
        await asyncio.sleep(10)
        return False

    return True

def signal_handler(sig, frame):
    global VLC_PROCESS, DEFAULT_VLC_CONNECT_HOST, DEFAULT_VLC_PORT
    print("Signal received, shutting down...")
    if VLC_PROCESS:
        try:
            VLC_PROCESS.terminate()
            print("VLC process terminated.")
        except Exception as e:
            print(f"Error stopping VLC: {e}")
    sys.exit(0)


async def main():
    global DEFAULT_VLC_ADVERTISE_HOST, DEFAULT_VLC_CONNECT_HOST, DEFAULT_VLC_PORT, VLC_PROCESS

    # Register the signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


    parser = argparse.ArgumentParser(description='WebSocket Client')
    parser.add_argument('--type', choices=['seeker', 'switcher'], default=DEFAULT_CLIENT_TYPE,
                        help='Client type (seeker or switcher)')
    parser.add_argument('--token', default=DEFAULT_AUTH_TOKEN,
                        help='Authentication token')
    parser.add_argument('--server', default=DEFAULT_SERVER_URL,
                        help='WebSocket server URL')
    parser.add_argument('--vlc-host', default=DEFAULT_VLC_ADVERTISE_HOST,
                        help='VLC host address (for seeker client)')
    parser.add_argument('--vlc-port', type=int, default=DEFAULT_VLC_PORT,
                        help='VLC port number (for seeker client)')
    parser.add_argument('--video', default=DEFAULT_VIDEO_PATH,
                        help='Path to video file (for seeker client)')

    args = parser.parse_args()
    client_type = args.type
    auth_token = args.token
    server_url = args.server
    video_path = args.video

    DEFAULT_VLC_ADVERTISE_HOST = args.vlc_host
    DEFAULT_VLC_PORT = args.vlc_port

    print(f"Starting client as {client_type}")
    print(f"Connecting to server at {server_url}")

    # Start VLC if this is a seeker client
    if client_type == "seeker":
        print(f"VLC connection: {DEFAULT_VLC_ADVERTISE_HOST}:{DEFAULT_VLC_PORT}")
        print(f"Video path: {video_path}")

        # Start VLC process
        VLC_PROCESS = start_vlc(video_path, DEFAULT_VLC_ADVERTISE_HOST, DEFAULT_VLC_PORT)

        # Wait for VLC to load video
        time.sleep(2)

        # Get video duration
        duration = get_video_duration(DEFAULT_VLC_CONNECT_HOST, DEFAULT_VLC_PORT)
        if duration > 0:
            # Seek to a random position between 0 and 80% of the video
            random_position = random.randint(0, int(duration * 0.8))
            print(f"Seeking to random position: {random_position} seconds")
            send_command_to_vlc(
                f"seek {random_position}", DEFAULT_VLC_ADVERTISE_HOST, DEFAULT_VLC_PORT)

    try:
        # Reconnection loop
        while True:
            connected = await connect_to_server(client_type, auth_token, server_url)
            if not connected:
                print("Connection failed. Reconnecting in 10 seconds...")
                await asyncio.sleep(10)
    finally:
        # Clean up VLC process when the client exits
        if VLC_PROCESS:
            try:
                VLC_PROCESS.terminate()
                print("VLC process terminated.")
            except Exception as e:
                print(f"Error stopping VLC: {e}")


if __name__ == "__main__":
    asyncio.run(main())
