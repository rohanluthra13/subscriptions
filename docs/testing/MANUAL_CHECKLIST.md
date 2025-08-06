# Manual Testing Checklist

## Pre-Deployment Testing Checklist

This checklist should be completed before any deployment to production. Check each item as you complete it.

### 🔐 Gmail OAuth Flow
- [ ] Click "Connect Gmail" button on dashboard
- [ ] OAuth redirect works correctly
- [ ] Callback URL processes successfully
- [ ] Connection status shows as "Connected"
- [ ] User email displays correctly
- [ ] Tokens are stored (check database - should be encrypted)
- [ ] Can disconnect and reconnect

### 📧 Email Sync Process
- [ ] Manual sync button triggers sync
- [ ] Progress indicator shows during sync
- [ ] Sync completes without errors
- [ ] Last sync time updates
- [ ] Email count is reasonable
- [ ] Subscriptions are detected (if emails contain subscriptions)
- [ ] Processed emails are marked in database

### 📊 Subscription Management
- [ ] Subscriptions display in table/list
- [ ] Can sort by amount, date, name
- [ ] Search functionality works
- [ ] Filter by status works (active/inactive/paused)
- [ ] Filter by category works
- [ ] Pagination works if many subscriptions

### ✏️ Edit Subscription
- [ ] Edit button opens dialog
- [ ] All fields are editable
- [ ] Save updates the subscription
- [ ] Cancel discards changes
- [ ] Changes reflect immediately in list

### 🗑️ Delete Subscription
- [ ] Delete button shows confirmation
- [ ] Confirm deletes the subscription
- [ ] Cancel keeps the subscription
- [ ] Deleted item removed from list

### 📥 Export Functionality
- [ ] Export button is visible
- [ ] CSV export downloads file
- [ ] JSON export downloads file
- [ ] Exported data is complete and correct
- [ ] File names include date

### 📈 Dashboard Statistics
- [ ] Monthly total calculated correctly
- [ ] Yearly total calculated correctly
- [ ] Active subscription count correct
- [ ] Category breakdown accurate
- [ ] Last sync time displayed

### 🔄 Background Sync (if enabled)
- [ ] Cron job runs at scheduled time
- [ ] Daily sync processes new emails only
- [ ] No duplicate subscriptions created
- [ ] Sync status tracked in database

### 🛡️ Security Checks
- [ ] No API keys visible in frontend
- [ ] No sensitive data in console logs
- [ ] API endpoints require authentication
- [ ] Tokens encrypted in database
- [ ] Environment variables not exposed

### 🎨 UI/UX Checks
- [ ] Responsive on desktop (1920x1080)
- [ ] Responsive on laptop (1366x768)
- [ ] Responsive on tablet (768x1024)
- [ ] Loading states display properly
- [ ] Error messages are user-friendly
- [ ] Success messages confirm actions
- [ ] No broken images or icons
- [ ] All links work correctly

### ⚡ Performance Checks
- [ ] Dashboard loads in < 2 seconds
- [ ] Subscription list loads quickly
- [ ] Search is responsive
- [ ] Export doesn't timeout
- [ ] No memory leaks in browser

### 🐛 Error Handling
- [ ] Network errors show message
- [ ] API errors display gracefully
- [ ] Form validation works
- [ ] Invalid data handled properly
- [ ] Can recover from errors

### 🚀 Deployment Readiness
- [ ] All environment variables set
- [ ] Database migrations run
- [ ] Docker containers start
- [ ] Health checks pass
- [ ] Can access application
- [ ] Gmail OAuth redirect URI updated for production

## Quick Smoke Test (5 minutes)

For quick validation after deployment:

1. **Connect Gmail** - OAuth flow completes
2. **Run Manual Sync** - Processes some emails
3. **View Subscriptions** - Data displays correctly
4. **Edit One Subscription** - Changes save
5. **Export Data** - File downloads
6. **Check Logs** - No critical errors

## Test Accounts

- Primary test account: `rohanluthra13@gmail.com`
- Ensure test account has subscription emails before testing

## Known Issues to Check

1. **Token Refresh** - May need to reconnect after 7 days
2. **Rate Limiting** - Gmail API has quotas
3. **Large Syncs** - First sync of 6 months may take time
4. **Duplicate Detection** - Fuzzy matching may have edge cases

## How to Report Issues

If you find issues during testing:

1. Note the exact steps to reproduce
2. Check browser console for errors
3. Check server logs for errors
4. Take screenshots if UI issues
5. Document in GitHub Issues

## Testing Commands

```bash
# Run integration tests
npm run test:integration

# Check types
npm run type-check

# Run linter
npm run lint

# Start dev environment
docker-compose up

# View logs
docker-compose logs -f app
```

## Sign-off

- [ ] All critical items checked
- [ ] No blocking issues found
- [ ] Ready for deployment

Tested by: _________________
Date: _________________
Version: _________________