export function Mascot({state='idle'}:{state?:string}) {
  return <svg className={`mitra-calf mitra-${state}`} viewBox="0 0 100 108" aria-hidden="true">
    <ellipse cx="50" cy="101" rx="27" ry="4" fill="#164e4220"/>
    <path d="M29 67Q16 72 20 90" fill="none" stroke="#926840" strokeWidth="5" strokeLinecap="round"/>
    <path d="M34 63Q50 54 68 66L74 86Q52 100 28 86Z" fill="#f0ddbc" stroke="#584934" strokeWidth="2"/>
    <path d="M35 86v9h10v-8M57 87v8h10v-9" fill="#725a40" stroke="#584934" strokeWidth="2" strokeLinejoin="round"/>
    <path d="M29 29Q13 13 7 31Q16 42 30 39M71 29Q87 13 93 31Q84 42 70 39" fill="#dbc49e" stroke="#584934" strokeWidth="2"/>
    <path d="M16 28l11 6M84 28l-11 6" stroke="#c89283" strokeWidth="5" strokeLinecap="round"/>
    <path d="M30 24Q23 12 32 8L37 23M63 23l5-15q9 4 2 16" fill="#f5ecd9" stroke="#584934" strokeWidth="2"/>
    <path d="M27 29Q31 13 51 17Q72 13 76 34L73 56Q67 72 48 72Q26 70 24 52Z" fill="#fcf4df" stroke="#584934" strokeWidth="2"/>
    <path d="M31 23Q44 14 48 24L41 45Q30 49 26 39Z" fill="#b28759"/>
    <path d="M46 21q-5-12 8-12l6 12" fill="#b28759"/>
    <g className="mitra-eyes"><ellipse cx="36" cy="39" rx="3.4" ry="4.7" fill="#283e36"/><ellipse cx="64" cy="39" rx="3.4" ry="4.7" fill="#283e36"/><circle cx="37" cy="37" r="1.2" fill="white"/><circle cx="65" cy="37" r="1.2" fill="white"/></g>
    <ellipse cx="50" cy="57" rx="22" ry="14" fill="#e6bd98"/>
    <ellipse cx="40" cy="53" rx="2.5" ry="3" fill="#775e47"/><ellipse cx="60" cy="53" rx="2.5" ry="3" fill="#775e47"/>
    <path className="mitra-mouth" d="M44 61q6 5 12 0" stroke="#775e47" strokeWidth="2" fill="none" strokeLinecap="round"/>
    <path d="M31 72q19 9 39 0l-4 10q-17 6-33-1Z" fill="#087f6c"/><path d="m64 79 10 10-15-1" fill="#096d5d"/>
    <circle cx="50" cy="83" r="5" fill="#e8bd57" stroke="#ab833c"/><path d="M50 80v6m-3-3h6" stroke="#725b2f"/>
  </svg>
}
