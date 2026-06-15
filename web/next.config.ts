import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Standalone output produces a self-contained server bundle for a slim
  // container image (see web/Dockerfile). The camera/liveness step is
  // client-only; nothing here needs a custom server runtime.
  output: "standalone",
};

export default nextConfig;
