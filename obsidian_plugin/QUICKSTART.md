# WriterOS Obsidian Plugin - Quick Start

## ✅ Build Complete!

The plugin has been successfully built. You now have:
- `main.js` - The compiled plugin
- `manifest.json` - Plugin metadata

## 📦 Installation Steps

### Step 1: Locate Your Obsidian Vault

Find the folder where your Obsidian vault is stored. For example:
- `C:\Users\YourName\Documents\MyVault`
- `D:\Obsidian\MyStories`

### Step 2: Run the Installer

Open PowerShell in this directory and run:

```powershell
.\install.ps1 -VaultPath "C:\Path\To\Your\Vault"
```

**Replace** `C:\Path\To\Your\Vault` with your actual vault path!

### Step 3: Enable in Obsidian

1. Open Obsidian
2. Go to **Settings** (gear icon)
3. Click **Community plugins**
4. Turn **OFF** "Safe mode" (if it's on)
5. Find **WriterOS** in the list
6. Toggle it **ON**
7. Press **Ctrl+R** to reload Obsidian

### Step 4: Verify It Works

1. Press **Ctrl+P** to open Command Palette
2. Type "WriterOS"
3. You should see commands like:
   - WriterOS: Open Relationship Graph
   - WriterOS: Open Family Tree
   - WriterOS: Start Server
   - WriterOS: Open Chat

## ⚙️ Configuration

After enabling the plugin:

1. Go to **Settings** → **WriterOS**
2. Set **Python Path**:
   ```
   C:\Users\rahme\AppData\Local\Programs\Python\Python313\python.exe
   ```
3. Set **Script Path** (for graph generation):
   ```
   C:\Users\rahme\IdeaProjects\YouTube Transcript Agent\generate_graph.py
   ```
4. Set **Server Path** (for chat/agents):
   ```
   C:\Users\rahme\IdeaProjects\YouTube Transcript Agent\server.py
   ```

## 🧪 Testing

### Test Graph Generation

1. Open Command Palette (Ctrl+P)
2. Run: `WriterOS: Open Relationship Graph`
3. Should generate and open a graph in your browser

### Test Chat (Phase 5)

1. Run: `WriterOS: Start Server`
2. Wait for "WriterOS Server Started!" notification
3. Run: `WriterOS: Open Chat`
4. Type a message and press Enter

## 🐛 Troubleshooting

### Plugin doesn't show up

- Check that files are in: `YourVault\.obsidian\plugins\writeros\`
- Make sure both `main.js` and `manifest.json` are there
- Reload Obsidian (Ctrl+R)

### Commands don't appear

- Make sure the plugin is **enabled** in Settings
- Reload Obsidian (Ctrl+R)
- Check Developer Console (Ctrl+Shift+I) for errors

### Graph generation fails

- Verify Python path in settings
- Make sure the script path points to `generate_graph.py`
- Check that PostgreSQL is running

### Server won't start

- Verify server path in settings
- Make sure PostgreSQL is running
- Check port 8000 isn't already in use

## 📝 What's Your Vault Path?

Tell me your Obsidian vault path and I can give you the exact command to run!
