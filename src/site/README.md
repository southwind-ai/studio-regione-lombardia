# Case Study Static Website

This directory contains the static website for the Regione Lombardia pagoPA case study.

## Overview

The website is **completely static** - all report links are embedded at build time during the GitHub Actions workflow. No backend server or runtime API calls are needed.

## How It Works

1. **Daily Workflow** (`daily-report.yml`):
   - Fetches new data and creates a report via Southwind AI API
   - Waits for the report to complete (polling the status endpoint)
   - Runs `build_site.py` to generate a static HTML with all report links
   - Commits the generated `index.html` to the repository
   - Deploys to Cloudflare Pages

2. **Build Script** (`build_site.py`):
   - Fetches all available reports from the API
   - Gets embed URLs for each report
   - Generates `index.html` from `index.template.html`
   - Replaces placeholders with actual report links
   - Completely static output - no JavaScript API calls needed

## Files

- **index.template.html** - HTML template with placeholders
- **index.html** - Generated static HTML (auto-generated, do not edit manually)
- **build_site.py** - Build script that generates the static site

## Local Development

### Building the Site Locally

```bash
# Make sure you have your API_KEY in .env
cd src/site
python3 build_site.py
```

This will generate `index.html` with all current reports.

### Viewing the Site Locally

Since it's a static HTML file, you can simply open it in a browser or serve it:

```bash
# Option 1: Open directly
open index.html

# Option 2: Serve with Python
python3 -m http.server 8000
# Then open http://localhost:8000/index.html
```

### Rebuilding After Changes

If you modify `index.template.html`, rebuild the site:

```bash
python3 build_site.py
```

## Environment Variables

The build script uses these environment variables:

- `API_KEY` - Southwind AI API key (required)
- `API_BASE` - API base URL (default: https://app.southwind.ai/api)
- `NEW_REPORT_ID` - If set, wait for this specific report to complete before building

## Template Placeholders

The template uses these placeholders:

- `{{LATEST_REPORT_URL}}` - URL of the most recent report
- `{{REPORT_LIST}}` - HTML list items for all reports
- `{{BUILD_TIME}}` - Timestamp when the site was built

## Deployment

### Cloudflare Pages

The GitHub Actions workflow automatically deploys to Cloudflare Pages. You need to set these secrets in your repository:

- `CLOUDFLARE_API_TOKEN` - API token for Cloudflare
- `CLOUDFLARE_ACCOUNT_ID` - Your Cloudflare account ID

The project name is configured as `studio-regione-lombardia` in the workflow.

### Alternative Deployment

Since this is a static site, you can deploy it anywhere:

- **GitHub Pages**: Push `index.html` to a gh-pages branch
- **Netlify**: Point to the `src/site` directory
- **Vercel**: Deploy the `src/site` directory
- **S3 + CloudFront**: Upload `index.html` and assets

## Manual Site Rebuild

To manually rebuild the site without creating a new report:

1. Go to the Actions tab in GitHub
2. Select "Rebuild Static Site" workflow
3. Click "Run workflow"

Or trigger locally:

```bash
python3 src/site/build_site.py
```

## Advantages of This Approach

✅ **No backend required** - Just static HTML, served fast from CDN  
✅ **Secure** - API key never exposed to clients  
✅ **Fast** - No runtime API calls, instant page load  
✅ **Reliable** - No server to maintain or crash  
✅ **Free hosting** - Static hosting is free on most platforms  
✅ **Version controlled** - Generated HTML is committed to git

## Development Tips

1. Always edit `index.template.html`, never `index.html` (it gets overwritten)
2. Test locally before committing template changes
3. The build script validates all API responses
4. Report polling waits up to 30 minutes for completion
