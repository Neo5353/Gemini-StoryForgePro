import { useRef, useEffect, useState } from 'react';
import { Stage, Layer, Rect, Image as KonvaImage, Group } from 'react-konva';
import type { PageData, PanelData } from '../../types';
import { SpeechBubble } from './SpeechBubble';

interface PanelCanvasProps {
  page: PageData;
  width?: number;
  height?: number;
}

const PADDING = 8;
const GUTTER = 6;

function useImageLoader(url: string | null): HTMLImageElement | null {
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  useEffect(() => {
    if (!url) return;
    const image = new window.Image();
    image.crossOrigin = 'anonymous';
    image.onload = () => setImg(image);
    image.src = url;
  }, [url]);
  return img;
}

function PanelCell({ panel, x, y, w, h }: {
  panel: PanelData;
  x: number;
  y: number;
  w: number;
  h: number;
}) {
  const img = useImageLoader(panel.image_url);

  return (
    <Group x={x} y={y}>
      {/* Panel border */}
      <Rect width={w} height={h} fill="#1a1a1a" stroke="#333" strokeWidth={2} cornerRadius={4} />

      {/* Image */}
      {img && (
        <KonvaImage
          image={img}
          x={2}
          y={2}
          width={w - 4}
          height={h - 4}
          cornerRadius={3}
        />
      )}

      {/* Placeholder if no image */}
      {!img && (
        <>
          <Rect x={2} y={2} width={w - 4} height={h - 4} fill="#262626" cornerRadius={3} />
          <Rect
            x={w / 2 - 20}
            y={h / 2 - 2}
            width={40}
            height={4}
            fill="#404040"
            cornerRadius={2}
          />
        </>
      )}

      {/* Speech bubbles */}
      {panel.bubbles.map((bubble) => (
        <SpeechBubble key={bubble.id} bubble={bubble} />
      ))}
    </Group>
  );
}

function computePanelLayout(page: PageData, canvasW: number, canvasH: number) {
  const innerW = canvasW - PADDING * 2;
  const innerH = canvasH - PADDING * 2;

  // Determine grid dimensions from layout
  const layoutMap: Record<string, [number, number]> = {
    '2x2': [2, 2],
    '3x2': [3, 2],
    '2x3': [2, 3],
    '3x3': [3, 3],
    splash: [1, 1],
    vertical_strip: [1, 4],
    dynamic: [2, 3],
  };

  const [cols, rows] = layoutMap[page.layout] ?? [2, 2];
  const cellW = (innerW - GUTTER * (cols - 1)) / cols;
  const cellH = (innerH - GUTTER * (rows - 1)) / rows;

  return page.panels.map((panel) => ({
    panel,
    x: PADDING + panel.position.col * (cellW + GUTTER),
    y: PADDING + panel.position.row * (cellH + GUTTER),
    w: cellW * panel.span.cols + GUTTER * (panel.span.cols - 1),
    h: cellH * panel.span.rows + GUTTER * (panel.span.rows - 1),
  }));
}

export function PanelCanvas({ page, width = 800, height = 1100 }: PanelCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: width, h: height });

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        const w = entry.contentRect.width;
        setSize({ w, h: w * 1.375 }); // Comic page aspect ratio
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const layout = computePanelLayout(page, size.w, size.h);

  return (
    <div ref={containerRef} className="w-full rounded-xl overflow-hidden border border-neutral-700/50 bg-neutral-900">
      <Stage width={size.w} height={size.h}>
        <Layer>
          {/* Page background */}
          <Rect width={size.w} height={size.h} fill="#0f0f0f" />

          {layout.map(({ panel, x, y, w, h }) => (
            <PanelCell key={panel.id} panel={panel} x={x} y={y} w={w} h={h} />
          ))}
        </Layer>
      </Stage>
    </div>
  );
}
