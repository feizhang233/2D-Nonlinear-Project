/**
 * Nonlinear Studio process manager.
 *
 * - API + workbench: Docker Compose (`nonlinear-studio` on 127.0.0.1:8007)
 * - Public hostname: nonlinear.feizhang233.com
 *   (dedicated Cloudflare tunnel, config-nonlinear.yml)
 */
module.exports = {
  apps: [
    {
      name: "nonlinear-tunnel",
      cwd: "/home/fei/Solver/2D-nonlinear-project",
      script: "/usr/bin/cloudflared",
      args: "--no-autoupdate --config /home/fei/.cloudflared/config-nonlinear.yml tunnel run",
      interpreter: "none",
      max_restarts: 20,
      min_uptime: "5s",
    },
  ],
};
