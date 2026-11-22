import '@/app/globals.css';
import Navbar from '@/components/Navbar';

export const metadata = {
  title: 'ResumeAI - AI-Powered Resume Matching',
  description: 'Find your perfect job match with AI-powered resume analysis',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <Navbar />
        <main>{children}</main>
      </body>
    </html>
  );
}
