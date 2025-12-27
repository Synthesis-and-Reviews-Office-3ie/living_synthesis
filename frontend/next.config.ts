import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
  // Disable Turbopack to avoid long path issues on Windows
  turbopack: {
    root: ".",
  },
};

export default nextConfig;
