import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The camera/liveness step is client-only; nothing here needs server runtime.
};

export default nextConfig;
