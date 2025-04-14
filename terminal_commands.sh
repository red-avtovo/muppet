# Update Node.js using nvm (if installed)
# If you don't have nvm installed, you can install it with:
# curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# After nvm is installed and your terminal is restarted:
nvm install --lts  # Install latest LTS version
nvm use --lts      # Use the LTS version

# Alternatively, update Node.js using Homebrew (since you're on macOS):
brew update
brew upgrade node

# After updating Node.js, try installing the package again:
sudo npm install -g @anthropic-ai/claude-code

