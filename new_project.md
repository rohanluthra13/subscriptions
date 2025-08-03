# New Project Setup

Fill in the following details:

**Project Information:**
- Project Name: [subscriptions]
- GitHub Username: [rohanluthra13]
- Repository Name: [subscriptions]

**Setup Commands:**

Once you've filled in the above, run these commands:

```bash
# 1. Initialize git repository
git init

# 2. Create initial project structure
mkdir src
touch src/index.js

# 3. Initialize npm project
npm init -y

# 4. Create .gitignore
echo "node_modules/
.env
.DS_Store
*.log" > .gitignore

# 5. Create README
echo "# [YOUR_PROJECT_NAME]

leave blank

## Setup
\`\`\`bash
npm install
\`\`\`" > README.md

# 6. Initial commit
git add .
git commit -m "Initial commit"

# 7. Create GitHub repository (using GitHub CLI)
gh repo create [YOUR_GITHUB_USERNAME]/[YOUR_REPO_NAME] --public --source=. --remote=origin --push
```

**Alternative (without GitHub CLI):**
1. Create repository on GitHub.com manually
2. Run:
```bash
git remote add origin https://github.com/[YOUR_GITHUB_USERNAME]/[YOUR_REPO_NAME].git
git branch -M main
git push -u origin main
```
