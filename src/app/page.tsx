export default function Home() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <main className="text-center px-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-6">
          Subscription Tracker
        </h1>
        <p className="text-xl text-gray-600 mb-8 max-w-2xl">
          Automatically detect and track your subscriptions using AI-powered email analysis
        </p>
        <div className="space-y-4">
          <button className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors">
            Connect Gmail
          </button>
          <p className="text-sm text-gray-500">
            We&apos;ll analyze your emails to find subscriptions automatically
          </p>
        </div>
      </main>
    </div>
  );
}