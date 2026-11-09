import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useI18n } from '../context.jsx';

const pinLabel = (price) => {
  if (!price) return '•';
  return price >= 1_000_000 ? `${(price / 1_000_000).toFixed(1)}M` : `${Math.round(price / 1000)}k`;
};

// The first view covers ads near campus; farther ones appear when zooming out.
const NEAR_CAMPUS_KM = 6;

const escapeHtml = (text) => String(text).replace(/[&<>"']/g, (char) => `&#${char.charCodeAt(0)};`);

const pinIcon = (label, className) =>
  L.divIcon({ className: 'pin-wrap', html: `<span class="pin ${className}">${escapeHtml(label)}</span>`, iconSize: null });

/** A real, draggable 2GIS map. Tiles come through our server, never with the key. */
export default function ListingsMap({ items, sdu, height = 380, activeId = null }) {
  const { t, path } = useI18n();
  const navigate = useNavigate();
  const box = useRef(null);
  const map = useRef(null);
  const markers = useRef(new Map());

  useEffect(() => {
    const instance = L.map(box.current, { scrollWheelZoom: false, zoomSnap: 0.5, minZoom: 8, maxZoom: 18 });
    L.tileLayer('/api/map/tile/{z}/{x}/{y}', { attribution: '© <a href="https://2gis.kz" target="_blank" rel="noopener">2GIS</a>', maxZoom: 18 }).addTo(instance);
    // Scrolling the page should not zoom the map until someone clicks it.
    instance.on('click', () => instance.scrollWheelZoom.enable());
    instance.on('mouseout', () => instance.scrollWheelZoom.disable());
    map.current = instance;
    return () => {
      instance.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !sdu) return undefined;
    const layer = L.layerGroup().addTo(instance);
    const placed = new Map();
    L.marker([sdu.lat, sdu.lon], { icon: pinIcon(t('sduPin'), 'sdu'), title: 'SDU University', keyboard: false, zIndexOffset: 1000 }).addTo(layer);
    const located = items.filter((item) => item.point);
    for (const item of located) {
      const marker = L.marker([item.point.lat, item.point.lon], { icon: pinIcon(pinLabel(item.price), ''), title: item.title, riseOnHover: true })
        .on('click', () => navigate(path(`/listing/${item.id}`)))
        .addTo(layer);
      placed.set(item.id, marker);
    }
    markers.current = placed;
    const near = located.filter((item) => item.distanceKm !== null && item.distanceKm <= NEAR_CAMPUS_KM);
    const focus = near.length >= 2 ? near : located;
    const points = [[sdu.lat, sdu.lon], ...focus.map((item) => [item.point.lat, item.point.lon])];
    if (points.length === 1) instance.setView(points[0], 15);
    else instance.fitBounds(points, { padding: [40, 40], maxZoom: 16 });
    return () => layer.remove();
  }, [items, sdu, navigate, path, t]);

  useEffect(() => {
    for (const [id, marker] of markers.current) {
      marker.getElement()?.querySelector('.pin')?.classList.toggle('active', id === activeId);
      marker.setZIndexOffset(id === activeId ? 2000 : 0);
    }
  }, [activeId, items]);

  return (
    <div>
      <div ref={box} className="leaflet-box" style={{ height }} role="region" aria-label={t('mapAlt')} />
      <p className="meta mapnote">{t('mapNote')}</p>
    </div>
  );
}
