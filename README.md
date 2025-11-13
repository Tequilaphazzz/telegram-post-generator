# 🚀 Telegram Post Generator

A Flask web application for automatically generating and publishing posts to Telegram using AI.

## 📋 Features

- ✨ Generate post text via ChatGPT 4o
- 🎨 Create images via Stability AI (Stable Diffusion 3)
- 📝 Automatically overlay headlines on images
- 📱 Publish to Telegram groups and Stories
- 🔄 Ability to regenerate individual elements
- ✅ Content approval before publishing
- 💾 Save API settings

## 🛠️ Installation

### 1. Clone the repository

```bash
mkdir telegram-post-generator
cd telegram-post-generator
````

### 2\. Create the project structure

Create the following folders:

```bash
mkdir templates static utils
```

### 3\. Install dependencies

```bash
pip install -r requirements.txt
```

### 4\. Install Roboto font (optional)

For correct display of Cyrillic (or other non-Latin) characters on images:

**Ubuntu/Debian:**

```bash
sudo apt-get install fonts-roboto
```

**Windows:**
Download Roboto from [Google Fonts](https://fonts.google.com/specimen/Roboto) and install it in the system.

**macOS:**

```bash
brew tap homebrew/cask-fonts
brew install --cask font-roboto
```

### 5\. Obtain API Keys

#### OpenAI API Key

1.  Go to [platform.openai.com](https://platform.openai.com)
2.  Navigate to API Keys
3.  Create a new key

#### Stability.ai API Key

1.  Go to [platform.stability.ai](https://platform.stability.ai)
2.  Register/Login
3.  Get the API key in settings

#### Telegram API

1.  Go to [my.telegram.org](https://my.telegram.org)
2.  Log in with your phone number
3.  Create an application in the "API development tools" section
4.  Get `api_id` and `api_hash`

## 🚀 Launch

1.  Start the application:

<!-- end list -->

```bash
python app.py
```

2.  Open your browser and go to:

<!-- end list -->

```
http://localhost:5000
```

## 📖 Usage

### Step 1: Configuration

1.  Enter all API keys in the "API Settings" section
2.  Specify the username or ID of your Telegram group
3.  Click "Save Settings"

### Step 2: Content Generation

1.  Enter a topic for the post
2.  Click "Generate Content"
3.  Wait for generation (may take 1-2 minutes)

### Step 3: Review and Approval

1.  Review the generated text
2.  Check the image with the overlaid headline
3.  If necessary, regenerate individual elements
4.  Approve each element with the "✅" buttons

### Step 4: Publication

1.  After approving all elements, click "Publish to Telegram"
2.  On the first launch, enter the confirmation code from Telegram
3.  The post will be published to the group and Stories

## 🔧 Configuration

Settings are saved in the `config.json` file and include:

  - API keys
  - Telegram credentials
  - Group ID/username

## 📝 Notes

### Limits and Restrictions

  - Post text: maximum 1500 characters
  - Headline on image: maximum 5 words
  - Image format: 9:16 (1080x1920) for Stories

### Telegram Stories

  - Stories are published for 24 hours
  - Requires Telegram Premium for some features
  - The image is automatically cropped to 9:16 format

### Error Handling

  - All errors are displayed in the web interface
  - If there are API problems, check the keys
  - Two-factor authentication may be required for Telegram

## 🐛 Troubleshooting

### Problem: "Error generating image"

**Solution:** Check your balance on Stability.ai and the correctness of the API key

### Problem: "Could not find group"

**Solution:** Make sure that:

  - You are an administrator of the group
  - The group username is specified correctly (without @)
  - Or use the numerical group ID

### Problem: "Text on the image is displayed incorrectly"

**Solution:** Install the Roboto font or check the font paths in `config.py`


## 🤝 Support

If you encounter problems, create an issue in the project repository.

