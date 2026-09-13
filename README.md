# 🚀 Ultimate Video Converter (Unraid WebUI)

A sleek, lightweight Python & FFmpeg-powered WebUI to batch-convert and repair your video libraries directly from your Unraid server disks with smart folder navigation and automated notifications.

## ✨ Features
* **Interactive Tree-View Browser:** Browse and expand your Unraid `/media` share directly within the app. Select individual sub-folders or your entire library with smart duplicate filtering.
* **Dynamic FFmpeg Engine:** Automatically parses and lists all available container formats, video codecs (such as `libx265`, `libx264`, `copy`), and audio codecs natively.
* **🛠️ Video Repair & Error Recovery:** Optional checkbox mode to fix corrupted videos, broken indexes, or damaged headers by ignoring stream errors (`-err_detect ignore_err`).
* **Fire-and-Forget Background Processing:** Start a conversion batch queue and safely close the browser tab. The container runs continuously in the background.
* **Discord Webhook Integration:** Receive instant, automated summary notifications in your Discord channel as soon as your conversion queue completes.
* **SSD Cache Management:** Automatically routes temporary working files through a dedicated `/cache` directory to speed up processing and protect your array drives.
* **Secure In-App Support Modal:** Built-in contact pop-up allowing users to send bug reports or questions directly from the WebUI, handled securely via backend routing without exposing webhook tokens.
* **Multi-Language & Fully Responsive:** Automatically adapts to your browser's system language natively and scales seamlessly from desktop monitors to mobile devices.

## 📡 Support & Contact
Heb je een vraag, een bug gevonden of een verzoek voor een nieuwe functie? Je kunt direct contact opnemen via de **Support & Contact** knop in de WebUI pop-up, of open een Issue op deze GitHub-repository!

☕ **Support & Buy Me a Coffee**
This project is developed with passion in my free time. If you enjoy using Ultimate Video Converter and want to help keep the app running, updated, and bug-free, please consider buying me a coffee!

👉 [Buy me a coffee via PayPal (PandaBoyNL)](https://www.paypal.com/paypalme/PandaBoyNL)

Thank you for your support! ❤️

## 📦 Unraid Installation
1. Go to the **Apps** tab (Community Applications) in Unraid.
2. Search for **Ultimate Video Converter**.
3. Click Install. 
4. **Important:** By default, this app uses port `8383`. If port `8383` is already in use on your server, please change the 'WebUI Port' (Host Port) during installation to another free port.

## 🛠️ Manual Docker Installation
If you prefer to run it via CLI:
```bash
docker run -d \
  --name ultimate-video-converter \
  -p 8383:8080 \
  -v /mnt/user/media:/media \
  -v /mnt/user/appdata/ultimate-converter/cache:/cache \
  -e DISCORD_WEBHOOK="your-discord-webhook-url" \
  pandaboynl/ultimate-video-converter:latest
