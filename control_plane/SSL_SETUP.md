# SSL Certificate Setup

## Problem
Self-signed certificates cause browser warnings ("Your connection is not private").

## Solution: Use mkcert

**mkcert** creates locally-trusted development certificates that browsers automatically trust.

### Option 1: Automatic (Docker - Recommended)
The control-plane container includes mkcert and will automatically generate trusted certificates on first startup.

**To regenerate certificates with mkcert:**

```bash
# Remove existing certificates
rm -rf control_plane/ssl/

# Restart control-plane (will auto-generate with mkcert)
docker compose restart control-plane

# Check logs to confirm mkcert was used
docker logs insightmesh-control-plane | grep mkcert
```

You should see:
```
Generating locally-trusted SSL certificates with mkcert...
Locally-trusted SSL certificates generated successfully (no browser warnings!)
```

### Option 2: Manual (Local Development)

If running control-plane locally outside Docker:

```bash
# Install mkcert (Mac)
brew install mkcert
mkcert -install

# Install mkcert (Linux)
wget https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-linux-amd64
sudo mv mkcert-v1.4.4-linux-amd64 /usr/local/bin/mkcert
sudo chmod +x /usr/local/bin/mkcert
mkcert -install

# Generate certificates
cd control_plane
rm -rf ssl/
./startup.sh  # Will use mkcert automatically
```

### Fallback: Self-Signed (with warnings)

If mkcert is not available, the startup script automatically falls back to OpenSSL self-signed certificates. You'll see browser warnings but it will still work.

To bypass the warning:
- Chrome/Edge: Click "Advanced" → "Proceed to localhost (unsafe)"
- Firefox: Click "Advanced" → "Accept the Risk and Continue"
- Safari: Click "Show Details" → "visit this website"

### Why mkcert?

- ✅ No browser warnings
- ✅ Trusted by all browsers automatically
- ✅ Simple to use
- ✅ Only affects local machine (safe)
- ✅ Perfect for development

### Verification

After regenerating certificates, visit `https://localhost:6001` - you should see a green lock icon with no warnings!
