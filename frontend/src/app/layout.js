import './globals.css';

export const metadata = {
    title: 'Docube Recommendation Service',
    description: 'Test Frontend for Recommendation Service E2E Testing',
};

export default function RootLayout({ children }) {
    return (
        <html lang="en">
            <head>
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet" />
            </head>
            <body>{children}</body>
        </html>
    );
}
