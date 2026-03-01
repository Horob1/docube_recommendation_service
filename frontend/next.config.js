/** @type {import('next').NextConfig} */
const nextConfig = {
    output: 'standalone',
    async rewrites() {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        return [
            {
                source: '/api/:path*',
                destination: `${apiUrl}/api/:path*`,
            },
            {
                source: '/health',
                destination: `${apiUrl}/health`,
            },
            {
                source: '/recommendations',
                destination: `${apiUrl}/recommendations`,
            },
            {
                source: '/interactions',
                destination: `${apiUrl}/interactions`,
            },
            {
                source: '/search-log',
                destination: `${apiUrl}/search-log`,
            },
        ];
    },
};

module.exports = nextConfig;
