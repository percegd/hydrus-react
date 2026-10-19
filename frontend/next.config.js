/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${process.env.HYDRUS_API_URL || "http://127.0.0.1:8001"}/:path*` },
    ];
  },
};

module.exports = nextConfig;
