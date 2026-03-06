Steam Server Browser (Enterprise Edition)

An enterprise-grade, multi-tabbed graphical user interface designed for high-performance querying, filtering, and connection management of Steam game servers. Engineered specifically to handle massive concurrent asynchronous requests using Valve's A2S protocol without UI thread locking.

Enterprise Architecture

This application utilizes a decoupled asyncio event loop running within an isolated QThread, allowing the main PyQt6 GUI loop to remain flawlessly responsive during massive network sweeps. It bypasses standard synchronous socket bottlenecks by leveraging native python-a2s coroutines.

Key Capabilities

Asynchronous A2S Interrogation: Processes 500+ master node queries concurrently via throttled semaphores.

Auto-FastDL Interception: Automatically interrogates target servers for sv_downloadurl endpoints, aggressively multithreading HTTP payload injections (maps, materials, models, sounds) prior to client launch.

Non-Blocking GUI: Fully responsive multi-tab interface with dynamic sorting and regex-capable filtering.

Seamless Steam Injection: Direct steam -applaunch sequence integration, stripping conflicting Python/Qt environment variables to prevent sandbox contamination.

Prerequisites

Python 3.10 or higher

Valid Steam API Key (Placed in a .env file)

Steam Client installed locally

Installation

git clone [https://github.com/YOUR_USERNAME/SteamServerBrowser.git](https://github.com/YOUR_USERNAME/SteamServerBrowser.git)
cd SteamServerBrowser
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt


Configuration

Ensure a .env file exists at your configured path (default: /home/tsann/Scripts/.env) containing your Steam API key:

STEAM_API_KEY=your_api_key_here


Usage

Execute the core application from the project root:

python3 src/main.py


License

This project is distributed under the MIT License. See LICENSE for more information.
