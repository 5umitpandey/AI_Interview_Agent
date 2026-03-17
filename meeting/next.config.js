/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  output: 'standalone',
  basePath: '/ai-led-interview-app',
  assetPrefix: '/ai-led-interview-app',
  trailingSlash: true,
  // ✅ ADD THIS BLOCK
  eslint: {
    ignoreDuringBuilds: true,
  },

  productionBrowserSourceMaps: true,

  images: {
    formats: ['image/webp'],
  },

  webpack: (config, { buildId, dev, isServer, defaultLoaders, nextRuntime, webpack }) => {
    config.module.rules.push({
      test: /\.mjs$/,
      enforce: 'pre',
      use: ['source-map-loader'],
      exclude: /@mediapipe/,
    });

    return config;
  },

  headers: async () => {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'Cross-Origin-Opener-Policy',
            value: 'same-origin',
          },
          {
            key: 'Cross-Origin-Embedder-Policy',
            value: 'credentialless',
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
