# Muppet

A Telegram-controlled WebSocket server with two client types: seekers and switchers.

## Overview

This system consists of:
1. A WebSocket server that also functions as a Telegram bot
2. Two types of clients (seekers and switchers) that connect to the server
3. Telegram commands that trigger actions on connected clients

## Server Setup

### Dependencies

To run the server, you need:

```bash
pip install python-telegram-bot websockets
```

For seeker clients, you'll also need:

```bash
pip install websockets
```

And VLC media player installed on the system.

### Configuration

1. Clone this repository
2. Edit `server.py` and replace `YOUR_TELEGRAM_BOT_TOKEN` with your actual Telegram bot token
   - To create a bot and get a token, talk to [@BotFather](https://t.me/botfather) on Telegram
3. For restricting access to a specific chat and enabling notifications:
   - Start the server with the default configuration
   - Send the `/getchatid` command to your bot in Telegram
   - Edit `server.py` and set `AUTHORIZED_CHAT_ID` to the chat ID displayed by the bot
4. By default, the WebSocket server runs on `localhost:8765` - edit the host/port in the code if needed

### Running the Server

```bash
python server.py
```

The server will start:
- WebSocket server on `ws://localhost:8765`
- Telegram bot that listens for commands

## Raspberry Pi Client Setup

Each client should be installed on a separate Raspberry Pi. The scripts in this repository automate the installation process.

### Installation

1. Copy the entire repository to your Raspberry Pi
2. Make the installation scripts executable:
   ```bash
   chmod +x *.sh
   ```
3. For seeker clients, ensure VLC is installed:
   ```bash
   sudo apt-get update
   sudo apt-get install vlc
   ```
4. Run the installation script as root, specifying the client type:
   ```bash
   sudo ./install.sh seeker
   # OR
   sudo ./install.sh switcher
   ```
   
This will:
- Install required dependencies
- Create a dedicated Python virtual environment
- Install the client as a systemd service that starts automatically on boot
- Set up proper configuration

### Configuration

During installation, a `config.py` file is created at `/opt/muppet/config.py` with the client type and server URL. 
You can edit this file to change:

- The server URL (if your server isn't on the default `ws://localhost:8765`)
- The authentication token (if you change it from the default)
- The VLC host and port (defaults to localhost:4212)
- The path to the video file (for seeker clients)

After changing the configuration, restart the service:

```bash
sudo ./restart.sh
```

### Management Scripts

The following scripts are included to help manage the client:

- `install.sh <seeker|switcher>` - Install the client as a specific type
- `update.sh` - Update an existing installation with new code
- `restart.sh` - Restart the client service
- `status.sh` - Check the status of the client service
- `logs.sh` - View real-time logs from the client
- `uninstall.sh` - Remove the client completely

## Running the Client Manually

If you prefer to run the client manually instead of as a service, install the dependencies and run:

```bash
python client.py --type seeker --video /path/to/your/video.mp4
# OR
python client.py --type switcher
```

You can also specify the server URL, authentication token, and VLC parameters:

```bash
python client.py --type seeker --server ws://server-ip:8765 --token your_auth_token --video /path/to/your/video.mp4 --vlc-host localhost --vlc-port 4212
```

## Telegram Commands

The following commands can be sent to your Telegram bot:

- `/seek [timecode]` - Sends the seek command with optional timecode (hh:mm:ss, mm:ss, or ss format) to a random subset of connected seeker clients (n/2+1)
- `/switch` - Sends the switch command to all connected switcher clients
- `/status` - Shows how many clients of each type are currently connected
- `/getchatid` - Returns your chat ID (useful for configuring the AUTHORIZED_CHAT_ID)

## Client Behavior

### Seeker Clients

Seeker clients receive `/seek` commands from the Telegram bot. When the `/seek` command is sent, 
a random subset of connected seeker clients (n/2+1) will receive the command.

Seeker clients control a VLC media player instance:
- When a seeker client starts, it launches VLC with a configured video file
- VLC starts playing the video from a random position
- When the client receives a `/seek [timecode]` command, it jumps to the specified position in the video
- Supported timecode formats: hh:mm:ss, mm:ss, or ss (e.g., 01:30:45, 5:20, or 45)

### Switcher Clients

Switcher clients receive `/switch` commands from the Telegram bot. When the `/switch` command is sent, 
all connected switcher clients will receive the command.

## Authentication

Each client authenticates to the server using a token and specifies its type. The default token is 
`secret_token_123` and can be changed in both the server and client code.

## Architecture

- The server maintains separate lists of seeker and switcher clients
- Telegram commands are processed and forwarded to the appropriate clients
- Clients identify themselves as either seekers or switchers when connecting
- The server ensures commands are only sent to clients of the appropriate type
- Clients automatically reconnect if the connection is lost
- The server can be restricted to only accept commands from a specific Telegram chat
- The server sends notifications when clients connect or disconnect

## Extending the System

To add more functionality:
1. Add new command handlers in the server's `main()` function
2. Implement the corresponding command processing in the client code

### VLC Control Functions

The seeker client provides VLC control capabilities through the telnet interface. Here are some functions you could add:

- Play/Pause control
- Volume adjustment
- Playback speed control
- Playlist management
- Screenshot capture

To add these features:
1. Update the server to send the appropriate command
2. Expand the client's command handling to process new commands
3. Use the `send_command_to_vlc()` function to control VLC

## Docker and Kubernetes Deployment

### Building the Docker Image

A multi-stage Dockerfile is provided to create a minimal image:

```bash
# Build the Docker image
./build-and-push.sh

# Build and push to a registry
./build-and-push.sh push

# Specify custom registry and tag
REGISTRY=my-registry.io IMAGE_NAME=my-org/muppet TAG=v1.0.0 ./build-and-push.sh push
```

### Deploying to Kubernetes

1. Edit the `deployment.yaml` file to set your configuration:
   - Set your Telegram bot token and authentication token in the Secret
   - Set your authorized chat ID if you want to restrict access
   - Update the image name if you're using a custom registry

2. Apply the Kubernetes manifests:
   ```bash
   kubectl apply -f deployment.yaml
   ```

3. Check the deployment status:
   ```bash
   kubectl get deployments
   kubectl get pods
   ```

4. View logs:
   ```bash
   kubectl logs -f deployment/muppet-server
   ```

For enhanced security, you can create the secret separately using kubectl:
```bash
kubectl create secret generic muppet-secrets \
  --from-literal=telegram-token=YOUR_TELEGRAM_BOT_TOKEN \
  --from-literal=auth-token=YOUR_AUTH_TOKEN
```

The deployment is configured with:
- Single replica with "Recreate" deployment strategy 
- Resource limits to prevent excessive resource usage
- Sensitive data stored in Kubernetes Secrets
- Liveness probe to ensure the WebSocket server is running