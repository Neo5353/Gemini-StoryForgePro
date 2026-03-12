import { Group, Shape, Text } from 'react-konva';
import type { SpeechBubbleData } from '../../types';

interface SpeechBubbleProps {
  bubble: SpeechBubbleData;
}

const BUBBLE_STYLES: Record<SpeechBubbleData['type'], {
  fill: string;
  stroke: string;
  textColor: string;
  dashEnabled: boolean;
}> = {
  speech: { fill: '#ffffff', stroke: '#333333', textColor: '#000000', dashEnabled: false },
  thought: { fill: '#f0f0f0', stroke: '#999999', textColor: '#333333', dashEnabled: true },
  narration: { fill: '#fef3c7', stroke: '#d97706', textColor: '#78350f', dashEnabled: false },
  shout: { fill: '#fef2f2', stroke: '#dc2626', textColor: '#991b1b', dashEnabled: false },
};

export function SpeechBubble({ bubble }: SpeechBubbleProps) {
  const style = BUBBLE_STYLES[bubble.type];
  const { x, y, width, height, text } = bubble;

  return (
    <Group x={x} y={y}>
      {/* Bubble shape */}
      <Shape
        sceneFunc={(ctx, shape) => {
          const rx = width / 2;
          const ry = height / 2;
          const cx = width / 2;
          const cy = height / 2;

          ctx.beginPath();

          if (bubble.type === 'thought') {
            // Cloud-like shape
            ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
          } else if (bubble.type === 'shout') {
            // Spiky shape
            const spikes = 12;
            for (let i = 0; i < spikes * 2; i++) {
              const angle = (i * Math.PI) / spikes;
              const r = i % 2 === 0 ? Math.max(rx, ry) * 1.1 : Math.min(rx, ry) * 0.85;
              const px = cx + Math.cos(angle) * r;
              const py = cy + Math.sin(angle) * r;
              if (i === 0) ctx.moveTo(px, py);
              else ctx.lineTo(px, py);
            }
            ctx.closePath();
          } else {
            // Rounded rectangle
            const r = 12;
            ctx.moveTo(r, 0);
            ctx.lineTo(width - r, 0);
            ctx.quadraticCurveTo(width, 0, width, r);
            ctx.lineTo(width, height - r);
            ctx.quadraticCurveTo(width, height, width - r, height);

            // Tail
            if (bubble.tail_direction === 'bottom') {
              ctx.lineTo(width * 0.55, height);
              ctx.lineTo(width * 0.45, height + 15);
              ctx.lineTo(width * 0.4, height);
            }

            ctx.lineTo(r, height);
            ctx.quadraticCurveTo(0, height, 0, height - r);
            ctx.lineTo(0, r);
            ctx.quadraticCurveTo(0, 0, r, 0);
          }

          ctx.fillStrokeShape(shape);
        }}
        fill={style.fill}
        stroke={style.stroke}
        strokeWidth={1.5}
        dash={style.dashEnabled ? [4, 4] : undefined}
        dashEnabled={style.dashEnabled}
        shadowColor="rgba(0,0,0,0.3)"
        shadowBlur={4}
        shadowOffsetY={2}
      />

      {/* Text */}
      <Text
        x={8}
        y={6}
        width={width - 16}
        height={height - 12}
        text={text}
        fontSize={12}
        fontFamily="'Comic Sans MS', 'Comic Neue', cursive"
        fill={style.textColor}
        align="center"
        verticalAlign="middle"
        wrap="word"
      />
    </Group>
  );
}
