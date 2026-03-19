/**
 * Vercel Serverless Function — /api/refresh
 * Triggers GitHub Actions workflow_dispatch to run the scraper.
 * Requires GITHUB_TOKEN env var (set in Vercel project settings).
 */
export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    return res.status(503).json({
      error: 'GITHUB_TOKEN not configured',
      fallback_url: 'https://github.com/kevin12596/00981a/actions/workflows/daily_scrape.yml',
    });
  }

  try {
    const response = await fetch(
      'https://api.github.com/repos/kevin12596/00981a/actions/workflows/daily_scrape.yml/dispatches',
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
          Accept: 'application/vnd.github.v3+json',
          'User-Agent': '00981a-etf-tracker',
        },
        body: JSON.stringify({ ref: 'master' }),
      }
    );

    if (response.status === 204) {
      return res.status(200).json({
        success: true,
        message: '已觸發資料更新，約 5-10 分鐘後完成',
      });
    }

    const body = await response.text();
    return res.status(response.status).json({ error: body });
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
}
