# ldkregar.com

Lori D. Kregar's website. A single static page, rebuilt every night by GitHub Actions and hosted free on GitHub Pages.

## How the papers update themselves

`build.py` asks Europe PMC for everything linked to Lori's ORCID (`0000-0001-7485-4509`), plus a title search for the upcoming bioRxiv preprint set in `config.json` under `featured`. Europe PMC indexes bioRxiv, so once the preprint is posted it shows up within a day or two. The "Coming soon" card then switches to a "Read the paper" link automatically.

Things Europe PMC doesn't index (like the PhD thesis) live in `data/manual.json`. Add to that file by hand if needed.

If Europe PMC is down during a nightly run, the build stops and the live site is left as it was.

**One thing to check:** Lori's ORCID record should list her works. In ORCID, use *Add works → Search & link → Europe PMC* (or Crossref) and import the Nature paper. When the preprint appears, add it the same way. The title watch catches the preprint even if she forgets.

## Editing

| What | Where |
|---|---|
| Substack link | `config.json` → `substack_url` (e.g. `"https://ldkregar.substack.com"`). Latest 3 posts then appear on the site automatically. |
| Featured paper title / summary | `config.json` → `featured` |
| Bio, research themes, talks | `template.html` |
| Extra publications | `data/manual.json` |

Preview locally without network: `python3 build.py --offline`, then open `dist/index.html`.

## One-time setup

1. **GitHub:** create a repository (e.g. `ldkregar-site`) and upload these files. Mac Finder hides the `.github` folder, so it may not upload: if it's missing, choose *Add file → Create new file*, type `.github/workflows/deploy.yml` as the name, and paste in the contents of `deploy-workflow-COPY.yml`.
2. **Pages:** in the repo, go to *Settings → Pages → Build and deployment → Source* and choose **GitHub Actions**. Then *Actions → Build and deploy → Run workflow*.
3. **Custom domain:** in *Settings → Pages → Custom domain*, enter `ldkregar.com` and save.
4. **GoDaddy DNS** (*My Products → ldkregar.com → DNS*): delete any existing `A` record for `@` (GoDaddy's "parked" page) and add:

   | Type | Name | Value |
   |---|---|---|
   | A | @ | 185.199.108.153 |
   | A | @ | 185.199.109.153 |
   | A | @ | 185.199.110.153 |
   | A | @ | 185.199.111.153 |
   | CNAME | www | `<github-username>.github.io` |

5. Wait for DNS (minutes to a few hours), then tick **Enforce HTTPS** in *Settings → Pages*.
