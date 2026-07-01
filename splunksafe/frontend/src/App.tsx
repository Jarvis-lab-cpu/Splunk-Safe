import Terminal from "./components/Terminal";

export default function App() {
  return (
    <div className="min-h-screen bg-[#0b0e14] flex items-center justify-center p-6">
      <div className="w-full max-w-4xl">
        <Terminal />
      </div>
    </div>
  );
}
