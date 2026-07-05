import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Lets the Docker prod build ship only the traced runtime deps, not
  // the full node_modules tree.
  output: "standalone",
};

export default nextConfig;
