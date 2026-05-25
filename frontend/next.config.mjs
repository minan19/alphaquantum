/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Build-time check ensures lint failures fail builds (CI-friendly)
  eslint: {
    ignoreDuringBuilds: false,
  },
};

export default nextConfig;
