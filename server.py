# pylint: disable=missing-docstring
import asyncio
import random
import os
from typing import Dict, List, Optional
import websockets
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from aiohttp import web

# Get configuration from environment variables with fallbacks
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "secret_token_123")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

# Authorized chat ID (messages from other chats will be ignored)
AUTHORIZED_CHAT_ID_STR = os.environ.get("AUTHORIZED_CHAT_ID", "")

AUTHORIZED_CHAT_ID: Optional[int] = None
try:
    AUTHORIZED_CHAT_ID = int(AUTHORIZED_CHAT_ID_STR)
except ValueError:
    AUTHORIZED_CHAT_ID = None

# Host and port configuration
# Default to all interfaces in container
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8765"))

# Client types
CLIENT_TYPE_SEEKER = "seeker"
CLIENT_TYPE_SWITCHER = "switcher"

# Organized clients by type
clients: Dict[str, List[websockets.ServerProtocol]] = {
    CLIENT_TYPE_SEEKER: [],
    CLIENT_TYPE_SWITCHER: []
}

# Additional client information
client_info: Dict[websockets.ServerProtocol, dict] = {}


async def broadcast_to_clients_by_type(message: str, client_type: str):
    """Broadcast message to all clients of a specific type."""
    if not clients[client_type]:
        print(f"No clients of type {client_type} connected")
        return

    disconnected = set()
    for client in clients[client_type]:
        try:
            await client.send(message)
        except websockets.exceptions.ConnectionClosed:
            disconnected.add(client)

    # Clean up any disconnected clients
    for client in disconnected:
        if client in clients[client_type]:
            clients[client_type].remove(client)
        client_info.pop(client, None)

    if disconnected:
        msg = f"Removed {len(disconnected)} disconnected {client_type} clients. " \
            f"Total {client_type} clients: {len(clients[client_type])}"
        await send_notification(f"⚠️ {msg}")
        print(msg)


async def broadcast_to_random_seekers(message: str):
    """Broadcast message to a random subset of seeker clients (n/2+1)."""
    seekers = clients[CLIENT_TYPE_SEEKER]
    if not seekers:
        print("No seeker clients connected")
        return

    # Calculate number of seekers to send to (n/2+1)
    num_recipients = max(1, (len(seekers) // 2) + 1)
    # Select random subset of seekers
    recipients = random.sample(seekers, min(num_recipients, len(seekers)))

    print(f"Broadcasting to {len(recipients)} of {len(seekers)} seekers")

    disconnected = set()
    for client in recipients:
        try:
            await client.send(message)
        except websockets.exceptions.ConnectionClosed:
            disconnected.add(client)

    # Clean up any disconnected clients
    for client in disconnected:
        if client in clients[CLIENT_TYPE_SEEKER]:
            clients[CLIENT_TYPE_SEEKER].remove(client)
        client_info.pop(client, None)

    if disconnected:
        msg = f"Removed {len(disconnected)} disconnected seeker clients. " \
            f"Total seeker clients: {len(clients[CLIENT_TYPE_SEEKER])}"
        print(msg)
        await send_notification(f"⚠️ {msg}")


async def send_notification(message):
    """Send notification to the authorized chat"""
    global application
    if AUTHORIZED_CHAT_ID and application:
        try:
            await application.bot.send_message(chat_id=AUTHORIZED_CHAT_ID, text=message)
        except Exception as e:
            print(f"Failed to send notification: {e}")


async def handle_connection(websocket: websockets.ServerProtocol):
    try:
        # Wait for the first message which should be the auth token and client type
        auth_message = await websocket.recv()

        # Parse auth message (format: "AUTH_TOKEN:CLIENT_TYPE")
        parts = auth_message.split(":", 1)
        if len(parts) != 2 or parts[0] != AUTH_TOKEN:
            # Send error message and close the connection
            await websocket.send("Authentication failed: Invalid token or format")
            await websocket.close(1008, "Unauthorized")
            return

        client_type = parts[1].lower()
        if client_type not in [CLIENT_TYPE_SEEKER, CLIENT_TYPE_SWITCHER]:
            await websocket.send(f"Invalid client type: {client_type}. Must be '{CLIENT_TYPE_SEEKER}' or '{CLIENT_TYPE_SWITCHER}'")
            await websocket.close(1008, "Invalid client type")
            return

        # Get client information from WebSocket
        client_ip = websocket.remote_address[0] if hasattr(
            websocket, 'remote_address') else 'unknown'

        # Check for X-Forwarded-For header
        x_forwarded_for = websocket.request.headers['X-Forwarded-For']
        if x_forwarded_for:
            # Use the first IP in the list, which is the original client IP
            client_ip = x_forwarded_for.split(',')[0].strip()

        # Add client to appropriate list
        clients[client_type].append(websocket)
        client_info[websocket] = {
            'type': client_type,
            'ip': client_ip,
            'connected_at': asyncio.get_event_loop().time(),
            'messages_received': 0
        }

        connection_msg = f"{client_type.capitalize()} client connected from {client_ip}. " \
            f"Total {client_type} clients: {len(clients[client_type])}"
        print(connection_msg)

        # Send notification to the authorized chat
        await send_notification(f"🟢 {connection_msg}")

        # Send welcome message
        await websocket.send(
            f"Authentication successful! Welcome to the WebSocket server as {client_type}."
        )

        # Handle incoming messages
        async for message in websocket:
            print(f"Received message from {client_type}: {message}")
            client_info[websocket]['messages_received'] += 1
            # Echo the message back
            await websocket.send(f"Server received: {message}")

    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Clean up when client disconnects
        client_type = client_info.get(websocket, {}).get('type')
        client_ip = client_info.get(websocket, {}).get('ip', 'unknown')

        if client_type and websocket in clients[client_type]:
            clients[client_type].remove(websocket)
            disconnect_msg = f"{client_type.capitalize()} client from {client_ip} disconnected. " \
                f"Total {client_type} clients: {len(clients[client_type])}"
            print(disconnect_msg)

            # Send notification to the authorized chat
            await send_notification(f"🔴 {disconnect_msg}")

        client_info.pop(websocket, None)


# Telegram command handlers
async def check_authorized(update: Update) -> bool:
    """Check if the message comes from an authorized chat."""
    if AUTHORIZED_CHAT_ID is None:
        # No restriction if AUTHORIZED_CHAT_ID is not set
        return True

    chat_id = update.effective_chat.id
    if chat_id != AUTHORIZED_CHAT_ID:
        await update.message.reply_text("Unauthorized: This bot only responds to messages from the authorized chat.")
        print(f"Rejected command from unauthorized chat ID: {chat_id}")
        return False
    return True


async def seek_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /seek command with optional timecode parameter."""
    if not await check_authorized(update):
        return

    seeker_count = len(clients[CLIENT_TYPE_SEEKER])
    if seeker_count == 0:
        await update.message.reply_text("No seeker clients connected.")
        return

    # Extract timecode from command arguments
    timecode = "0"  # Default to beginning of video if no timecode is provided
    if context.args:
        timecode = context.args[0]

    # Build seek command with timecode
    seek_command = f"/seek {timecode}"

    await update.message.reply_text(f"Sending seek command to {max(1, (seeker_count // 2) + 1)} of {seeker_count} seeker clients: {seek_command}")
    await broadcast_to_random_seekers(seek_command)


async def switch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /switch command."""
    if not await check_authorized(update):
        return

    switcher_count = len(clients[CLIENT_TYPE_SWITCHER])
    if switcher_count == 0:
        await update.message.reply_text("No switcher clients connected.")
        return

    await update.message.reply_text(f"Sending switch command to {switcher_count} switcher clients...")
    await broadcast_to_clients_by_type("/switch", CLIENT_TYPE_SWITCHER)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /status command to show connected clients."""
    if not await check_authorized(update):
        return

    seeker_count = len(clients[CLIENT_TYPE_SEEKER])
    switcher_count = len(clients[CLIENT_TYPE_SWITCHER])

    status_message = (
        f"Connected clients:\n"
        f"- Seekers: {seeker_count}\n"
        f"- Switchers: {switcher_count}\n"
        f"- Total: {seeker_count + switcher_count}"
    )

    await update.message.reply_text(status_message)


async def start_websocket_server():
    """Start the WebSocket server."""
    server = await websockets.serve(
        handle_connection,
        HOST,
        PORT,
    )
    print(f"WebSocket server started on ws://{HOST}:{PORT}")
    return server


# Global application object for sending notifications
application: Optional[Application] = None
websocket_server: Optional[websockets.ServerProtocol] = None


async def health_check(request):
    """Health check endpoint"""
    global websocket_server, application
    # check if the websocket and application are running
    if websocket_server and application:
        return web.Response(text="OK", status=200)
    else:
        return web.Response(text="Not OK", status=500)


async def start_http_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, 8080)  # You can choose a different port if needed
    await site.start()
    print(f"HTTP server started on http://{HOST}:8080/health")


async def main():
    global application, websocket_server
    # Set up the Telegram bot
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("seek", seek_command))
    application.add_handler(CommandHandler("switch", switch_command))
    application.add_handler(CommandHandler("status", status_command))

    # Add a command to display chat ID (useful for configuration)
    application.add_handler(CommandHandler(
        "getchatid", lambda u, c: u.message.reply_text(f"Your chat ID: {u.effective_chat.id}")))

    # Start the Telegram bot
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    print("Telegram bot started!")

    # Start WebSocket server
    websocket_server = await start_websocket_server()

    # Start HTTP server for health check
    await start_http_server()

    # Print configuration information
    print(f"WebSocket server started on ws://{HOST}:{PORT}")
    if AUTHORIZED_CHAT_ID:
        print(f"Authorized Chat ID: {AUTHORIZED_CHAT_ID}")
    else:
        print("No authorized chat ID set, all chats are allowed")
        print("Use /getchatid command in Telegram to get your chat ID for configuration")

    # Keep the application running
    try:
        await asyncio.Future()  # Run forever
    finally:
        # Clean shutdown
        await application.stop()
        websocket_server.close()
        await websocket_server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
