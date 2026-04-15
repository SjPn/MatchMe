/** @type {import('next').NextConfig} */
const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backend.replace(/\/$/, "")}/:path*`,
      },
    ];
  },
  async redirects() {
    return [
      { source: "/discussions", destination: "/timeline?tab=topics", permanent: false },
      { source: "/discussions/:path*", destination: "/timeline?tab=topics", permanent: false },
    ];
  },
};

export default nextConfig;
