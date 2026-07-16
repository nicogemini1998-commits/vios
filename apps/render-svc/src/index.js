// VIOS render-svc — M0 placeholder. Base futura para Remotion + FFmpeg (M11).
import { createServer } from "node:http";

const PORT = process.env.RENDER_PORT || 4010;

const server = createServer((req, res) => {
  if (req.url === "/health") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ status: "ok", service: "vios-render-svc", version: "0.0.1" }));
    return;
  }
  res.writeHead(404, { "content-type": "application/json" });
  res.end(JSON.stringify({ error: "not_found" }));
});

server.listen(PORT, () => console.log(`render-svc listening on :${PORT}`));
