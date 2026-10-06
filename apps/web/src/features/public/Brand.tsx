import { Link } from 'react-router-dom';

export function Brand({ light = false }: { light?: boolean }) {
  return <Link className={`sb-brand ${light ? 'sb-brand-light' : ''}`} to="/" aria-label="Syre Banks Fitness home"><span className="sb-brand-mark" aria-hidden="true">S<span>B</span></span><span className="sb-brand-name">SYRE BANKS<small>FITNESS</small></span></Link>;
}
