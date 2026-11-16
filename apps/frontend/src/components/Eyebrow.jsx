export default function Eyebrow({ bright = false, children }) {
  return (
    <div
      className={`text-[10px] font-bold uppercase tracking-[1.6px] ${
        bright ? "text-[#c4b5fd]" : "text-[#777783]"
      }`}
    >
      {children}
    </div>
  );
}
