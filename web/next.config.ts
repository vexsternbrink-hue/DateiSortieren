import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Das Dashboard ist vollständig nutzerbezogen und wird pro Request gerendert.
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
