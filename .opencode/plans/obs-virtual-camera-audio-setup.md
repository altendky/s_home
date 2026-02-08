# OBS Virtual Camera/Audio Setup Plan

**Goal**: Set up OBS as a centralized hub for webcam (with face tracking), audio input, and screen sharing that Google Meet, Discord, and Zoom can all use via virtual camera/microphone outputs.

**System**: Ubuntu 22.04, PipeWire 0.3.48, X11

---

## Phase 1: Install OBS Studio via Flatpak

### 1.1 Set up Flatpak (if needed)
```bash
# Check if flatpak is installed and has flathub remote
flatpak --version
flatpak remotes
```

If flathub isn't configured:
```bash
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
```

### 1.2 Install OBS Studio
```bash
flatpak install flathub com.obsproject.Studio
```

### 1.3 Initial test
- Launch OBS: `flatpak run com.obsproject.Studio`
- Complete the auto-configuration wizard
- Add a video source (Video Capture Device - your webcam)
- Click "Start Virtual Camera"
- Open a test app (could use a browser at https://webcamtests.com) and verify it sees "OBS Virtual Camera"

**Checkpoint**: Confirm virtual camera appears and shows your webcam feed.

---

## Phase 2: Set up PipeWire Virtual Audio Device

### 2.1 Create persistent virtual sink configuration
Create file: `~/.config/pipewire/pipewire.conf.d/obs-virtual-mic.conf`

Contents:
```
context.modules = [
    {   name = libpipewire-module-loopback
        args = {
            capture.props = {
                node.name = "OBS_Virtual_Mic_Capture"
                media.class = "Audio/Sink"
                audio.position = [ FL FR ]
            }
            playback.props = {
                node.name = "OBS_Virtual_Mic"
                media.class = "Audio/Source"
                audio.position = [ FL FR ]
            }
        }
    }
]
```

### 2.2 Restart PipeWire to load the config
```bash
systemctl --user restart pipewire pipewire-pulse
```

### 2.3 Verify virtual device exists
```bash
pactl list sources short | grep -i obs
```

Should show something like `OBS_Virtual_Mic`.

### 2.4 Configure OBS audio monitoring
- In OBS: Settings > Audio > Advanced > Monitoring Device
- Select the sink side ("OBS_Virtual_Mic_Capture" or similar)
- On your audio source, right-click > Advanced Audio Properties
- Set "Audio Monitoring" to "Monitor and Output" or "Monitor Only"

### 2.5 Test virtual mic
- Open a browser and go to a mic test site, or Discord/Meet settings
- Select "OBS_Virtual_Mic" as your microphone
- Speak and verify the audio passes through

**Checkpoint**: Confirm virtual mic works in a test app.

---

## Phase 3: Install obs-face-tracker Plugin into Flatpak

### 3.1 Download the plugin
```bash
cd /tmp
wget https://github.com/norihiro/obs-face-tracker/releases/download/0.9.1/obs-face-tracker-0.9.1-obs30-ubuntu-22.04-x86_64.deb
```

### 3.2 Extract plugin files from .deb
```bash
mkdir obs-face-tracker-extract
dpkg-deb -x obs-face-tracker-0.9.1-obs30-ubuntu-22.04-x86_64.deb obs-face-tracker-extract
```

### 3.3 Create Flatpak plugin directory
```bash
mkdir -p ~/.var/app/com.obsproject.Studio/config/obs-studio/plugins
```

### 3.4 Copy plugin files
The plugin from the .deb is typically in `/usr/lib/x86_64-linux-gnu/obs-plugins/` and data in `/usr/share/obs/obs-plugins/`. We need to restructure for Flatpak:

```bash
# Create plugin structure
mkdir -p ~/.var/app/com.obsproject.Studio/config/obs-studio/plugins/obs-face-tracker/bin/64bit
mkdir -p ~/.var/app/com.obsproject.Studio/config/obs-studio/plugins/obs-face-tracker/data

# Copy the .so file
cp obs-face-tracker-extract/usr/lib/x86_64-linux-gnu/obs-plugins/obs-face-tracker.so \
   ~/.var/app/com.obsproject.Studio/config/obs-studio/plugins/obs-face-tracker/bin/64bit/

# Copy data files
cp -r obs-face-tracker-extract/usr/share/obs/obs-plugins/obs-face-tracker/* \
   ~/.var/app/com.obsproject.Studio/config/obs-studio/plugins/obs-face-tracker/data/
```

### 3.5 Download HOG face detection model
The plugin needs a face detection model file. The .deb should include `dlib_hog_model/` in the data directory:

```bash
ls -la ~/.var/app/com.obsproject.Studio/config/obs-studio/plugins/obs-face-tracker/data/dlib_hog_model/
```

If the HOG model isn't included, it may need to be generated or downloaded separately.

### 3.6 Verify plugin loads
- Restart OBS
- Go to: Help > Log Files > View Current Log
- Search for "face-tracker" - should show it loading
- Or: Add a source, check if "Face Tracker" appears in the list

**Checkpoint**: Confirm face tracker plugin appears in OBS source/filter list.

---

## Phase 4: Configure and Test Complete Setup

### 4.1 Create a webcam scene with face tracking
1. Create a new Scene (e.g., "Webcam with Face Track")
2. Add Source > Video Capture Device (your webcam)
3. Right-click the source > Filters
4. Add Effect Filter > "Face Tracker"
5. Configure face tracker:
   - Detection method: HOG (default, lighter CPU)
   - Adjust zoom/pan sensitivity as desired
6. Close filters

### 4.2 Add audio source
1. In the same scene, your mic may already be captured via global audio
2. Or add Source > Audio Input Capture > select your mic
3. Optionally add audio filters (noise suppression, etc.)
4. Set audio monitoring to route through virtual mic (Advanced Audio Properties)

### 4.3 Test screen sharing sources
1. Add Source > Screen Capture (XSHM) - test full screen
2. Try the crop settings for partial screen
3. Add Source > Window Capture (Xcomposite) - test window capture
4. Create separate scenes for different sharing modes if desired

### 4.4 End-to-end test
1. Start Virtual Camera in OBS
2. Open Google Meet (or Discord/Zoom)
3. Select "OBS Virtual Camera" as camera
4. Select "OBS_Virtual_Mic" as microphone
5. Verify:
   - Video shows with face tracking working
   - Audio passes through
   - Screen sharing sources work when switched

**Checkpoint**: Full functionality confirmed in at least one of your target apps.

---

## Phase 5: (Optional) Quality of Life Improvements

- **Create scene collection**: Set up scenes for different use cases (webcam only, webcam + screen share, screen only)
- **Hotkeys**: Configure keyboard shortcuts to switch scenes or toggle face tracking
- **Profiles**: Save different configurations (maybe one with face tracking, one without for lower CPU)
- **Autostart**: Optionally configure OBS to start with your desktop session

---

## Reference: OBS Screen Capture Capabilities (Linux/X11)

| Capture Type | Description |
|-------------|-------------|
| **Screen Capture (XSHM)** | Captures entire monitor, with crop options (top/left/right/bottom) for portions |
| **Window Capture (Xcomposite)** | Captures specific window, ignores windows in front of it |

---

## Reference: HOG vs CNN Face Detection

- **HOG** (Histogram of Oriented Gradients): Lighter on CPU, slightly less accurate. Good starting point.
- **CNN** (Convolutional Neural Network): Heavier CPU usage, more accurate detection.

Switching between them is a dropdown in the face tracker filter properties - no reinstall needed.

---

## Potential Issues to Watch For

1. **Plugin library compatibility**: The .deb is built against system libraries; Flatpak is sandboxed. If the plugin fails to load, check library dependencies in OBS logs or try building from source.

2. **PipeWire virtual device not appearing**: May need to check PipeWire version or use alternative config syntax.

3. **Face tracker CPU usage too high**: Reduce detection frequency in filter settings, or switch to a non-tracked scene when not on camera.

4. **Screen capture permissions**: Flatpak may need additional permissions for screen capture. May need to grant via Flatseal or command line.
