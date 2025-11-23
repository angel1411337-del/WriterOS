# WriterOS Obsidian Plugin - Installation Guide

## Quick Installation Steps

### 1. Build the Plugin (if not already built)

```powershell
cd "c:\Users\rahme\IdeaProjects\YouTube Transcript Agent\obsidian_plugin"
npm install
npm run build
```

### 2. Install to Obsidian

You have two options:

#### Option A: Copy to Vault Plugins Folder (Recommended)

1. Open your Obsidian vault folder
2. Navigate to `.obsidian/plugins/` (create if it doesn't exist)
3. Create a folder called `writeros`
4. Copy these files from the plugin directory:
   - `main.js`
   - `manifest.json`
   - `styles.css` (if it exists)

**PowerShell Command:**
```powershell
# Replace YOUR_VAULT_PATH with your actual vault path
$vaultPath = "C:\Path\To\Your\Vault"
$pluginSource = "c:\Users\rahme\IdeaProjects\YouTube Transcript Agent\obsidian_plugin"
$pluginDest = "$vaultPath\.obsidian\plugins\writeros"

# Create plugin directory
New-Item -ItemType Directory -Force -Path $pluginDest

# Copy files
Copy-Item "$pluginSource\main.js" -Destination $pluginDest
Copy-Item "$pluginSource\manifest.json" -Destination $pluginDest
```

#### Option B: Symlink (For Development)

```powershell
# Replace YOUR_VAULT_PATH with your actual vault path
$vaultPath = "C:\Path\To\Your\Vault"
$pluginSource = "c:\Users\rahme\IdeaProjects\YouTube Transcript Agent\obsidian_plugin"
$pluginDest = "$vaultPath\.obsidian\plugins\writeros"

# Create symlink
New-Item -ItemType SymbolicLink -Path $pluginDest -Target $pluginSource
```

### 3. Enable the Plugin in Obsidian

1. Open Obsidian
2. Go to **Settings** → **Community plugins**
3. Make sure **Safe mode** is OFF
4. Click **Browse** or scroll to find **WriterOS**
5. Toggle it ON

### 4. Verify Installation

After enabling, you should see these commands in the Command Palette (Ctrl+P):

- `WriterOS: Open Relationship Graph`
- `WriterOS: Open Family Tree`
- `WriterOS: Open Faction Network`
- `WriterOS: Open Location Map`
- `WriterOS: Start Server`
- `WriterOS: Analyze Vault`
- `WriterOS: Open Chat`

## Troubleshooting

### Plugin Doesn't Show Up

1. **Check if files are in the right place:**
   ```
   YourVault/
   └── .obsidian/
       └── plugins/
           └── writeros/
               ├── main.js
               └── manifest.json
   ```

2. **Reload Obsidian:**
   - Close and reopen Obsidian
   - Or use Ctrl+R to reload

3. **Check the console for errors:**
   - Open Developer Tools: Ctrl+Shift+I
   - Look for errors in the Console tab

### Plugin Shows But Won't Enable

1. **Check manifest.json:**
   - Make sure `minAppVersion` matches your Obsidian version
   - Current setting: `0.15.0`

2. **Check main.js:**
   - Make sure it's not empty
   - Run `npm run build` again if needed

### Commands Don't Appear

1. **Verify plugin is enabled** in Settings → Community plugins
2. **Check Settings → WriterOS** for plugin-specific settings
3. **Reload Obsidian** (Ctrl+R)

## Configuration

After installation, configure the plugin:

1. Go to **Settings** → **WriterOS**
2. Set **Python Path** to your Python interpreter:
   ```
   C:\Users\rahme\AppData\Local\Programs\Python\Python313\python.exe
   ```
3. Set **Server Port** (default: 8000)
4. Set **Default Graph Type** (force, family, faction, or location)

## Testing the Plugin

### Test Graph Generation

1. Open Command Palette (Ctrl+P)
2. Run `WriterOS: Open Relationship Graph`
3. Should generate and open an HTML graph in your browser

### Test Chat (Phase 5)

1. Start the server: `WriterOS: Start Server`
2. Open chat: `WriterOS: Open Chat`
3. Type a message and verify streaming works

## File Structure

Your plugin folder should look like this:

```
obsidian_plugin/
├── main.js          ← Built JavaScript (required)
├── manifest.json    ← Plugin metadata (required)
├── main.ts          ← TypeScript source
├── api.ts           ← API client
├── views/
│   └── ChatView.ts  ← Chat UI
├── package.json
├── tsconfig.json
└── esbuild.config.mjs
```

## Need Help?

If you're still having issues:

1. Check the Obsidian console (Ctrl+Shift+I)
2. Verify the build succeeded: `npm run build`
3. Make sure all required files are copied
4. Try restarting Obsidian completely
