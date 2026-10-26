import type { InsightEntry } from '../model/catalog';
import { useState } from 'react';
import './insight-cover.scss';

export function InsightCover({ variant, imageUrl, background }: { variant: InsightEntry['cover']; imageUrl?: string; background?: string }) {
  const [failedUrl, setFailedUrl] = useState('');
  if (imageUrl && imageUrl !== failedUrl) return <div className="insight-cover insight-cover--image" style={{ backgroundColor: background }} aria-hidden="true"><img src={imageUrl} alt="" decoding="async" onError={() => setFailedUrl(imageUrl)} /></div>;
  return <div className={`insight-cover insight-cover--${variant}`} aria-hidden="true">
    <svg viewBox="0 0 600 340" fill="none" xmlns="http://www.w3.org/2000/svg">
      {variant === 'steel' ? <>
        <path d="M0 290 600 195V340H0Z" fill="#C14325" />
        <path d="m108 221 278-112 112 55-279 114Z" fill="#272826" />
        <path d="m108 221 111 57v35l-111-56Zm111 57 279-114v35L219 313Z" fill="#101C22" />
        {[0, 1, 2, 3, 4].map(i => <g key={i} transform={`translate(${i * 43} ${i * -17})`}>
          <path d="m120 190 112-47 50 25-113 46Z" fill="#E5DCD1" />
          <path d="m120 190 49 24v21l-49-24Z" fill="#606C6C" />
          <path d="m169 214 113-46v21l-113 46Z" fill="#27373A" />
          <path d="m126 192 42 20 108-44" stroke="#FFFAEB" strokeWidth="2" />
        </g>)}
        <circle cx="504" cy="66" r="28" stroke="#FFE4BD" strokeWidth="2" />
        <path d="M490 66h28m-14-14v28" stroke="#FFE4BD" strokeWidth="2" />
      </> : variant === 'contracts' ? <>
        <path d="M0 275 600 220v120H0Z" fill="#A8C4CF" />
        <path d="m173 66 242 18-18 242-242-18Z" fill="#517484" />
        <path d="m152 45 242 18-18 242-242-18Z" fill="#FCF9EF" />
        <path d="m194 108 130 10m-133 25 160 12m-163 24 123 9m-125 25 99 8" stroke="#B6B9B2" strokeWidth="5" />
        <path d="m307 209 56 4-4 55-26-18-30 14Z" fill="#D74632" />
        <circle cx="337" cy="203" r="29" fill="#E84E37" />
        <path d="m323 204 9 10 19-20" stroke="#FFF8E9" strokeWidth="4" />
        <path d="M96 51v27m-14-14h28m362 171v27m-14-14h28" stroke="#688A99" strokeWidth="2" />
      </> : <>
        <path d="M0 276 600 226v114H0Z" fill="#B2C4AF" />
        <path d="M126 250v-68h64v68m20 0V143h64v107m20 0V98h64v152m20 0V56h64v194" fill="#263D36" />
        <path d="M105 263c62 0 48-65 112-65s71-85 128-85 68-58 115-58" stroke="#E34B36" strokeWidth="7" />
        <path d="m442 46 22 7-8 22" stroke="#E34B36" strokeWidth="7" />
        <path d="M103 281h363" stroke="#6F8978" strokeWidth="2" />
        <circle cx="108" cy="87" r="24" stroke="#74917D" strokeWidth="2" />
        <path d="M101 88h16m-16 6h16m-13 9V73h7a8 8 0 0 1 0 16h-7" stroke="#74917D" strokeWidth="2" />
      </>}
    </svg>
  </div>;
}
