# Sources

## Active sources

| Source ID | Type | Competitor | Trust tier | URL / repo |
|---|---|---|---|---|
| sonatype-blog | rss | Sonatype | 1 | https://www.sonatype.com/blog/rss.xml |
| cloudsmith-blog | rss | Cloudsmith | 1 | https://cloudsmith.com/rss/blog.xml |
| jfrog-blog | rss | JFrog | 1 | https://jfrog.com/blog/feed/ |
| github-changelog | rss | GitHub | 2 | https://github.blog/changelog/feed/ |
| gitlab-releases | rss | GitLab | 2 | https://docs.gitlab.com/releases/all-releases.xml |
| snyk-blog | rss | Snyk | 3 | https://snyk.io/blog/feed/ |
| releases-nexus-public | github_releases | Sonatype | 1 | sonatype/nexus-public |
| releases-cloudsmith-cli | github_releases | Cloudsmith | 1 | cloudsmith-io/cloudsmith-cli |
| newsdata | newsdata | (query: JFrog OR Sonatype OR Cloudsmith OR Artifactory) | 3 | newsdata.io API |

Full definitions, competitor aliases, and per-source trust tiers live in
`config.toml`.

## Trust tier semantics

- **Tier 1**: first-party company blogs and release channels. The vendor's
  own words about its own product. Relevance is assumed by construction,
  the whole feed is on-topic.
- **Tier 2**: official changelogs of large platforms (GitHub, GitLab) that
  are not the tracked competitor itself but ship features relevant to the
  competitive space. Also assumed relevant by construction.
- **Tier 3**: third-party or news content (Snyk blog, general news search).
  Not vendor-controlled, so items must match a tracked competitor alias
  before they are treated as relevant (entity-match gating).

## Considered and dropped

- **GitLab blog, all-posts feed** (`about.gitlab.com/atom.xml`): kept only
  as a fallback candidate. The docs releases feed
  (`docs.gitlab.com/releases/all-releases.xml`) is scoped to releases and
  was confirmed working, so the noisier all-posts feed was not added.
- **GitHub Releases via the REST API**: dropped in favor of the public
  `.atom` feed per repo. The API alternative is rate-limited to 60
  requests/hour unauthenticated; the atom feed needs no auth and carries no
  such limit.

## GitHub releases feed choice

All `github_releases` sources use the public per-repo `.atom` feed
(`https://github.com/{owner}/{repo}/releases.atom`) rather than the GitHub
REST API. The atom feed requires no authentication and is not subject to
the unauthenticated API's 60 requests/hour rate limit, making it a better
fit for a scheduled polling pipeline.
