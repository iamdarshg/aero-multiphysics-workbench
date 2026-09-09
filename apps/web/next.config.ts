import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  experimental: { optimizePackageImports: ['@react-three/fiber'] },
};

export default nextConfig;
