import { memo } from 'react';
import { Box, Typography } from '@mui/material';
import { palette } from '../../theme';
import { CAMERA_EXTERNAL_URL, CAMERA_ZED_URL } from '../../constants';
import { useMjpegStream } from '../../hooks/useMjpegStream';

interface VisionCameraProps {
  connected?: boolean;
}

function VisionCameraInner({ connected = true }: VisionCameraProps) {
  const ext = useMjpegStream(CAMERA_EXTERNAL_URL, connected);
  const zed = useMjpegStream(CAMERA_ZED_URL, CAMERA_ZED_URL !== '' && connected);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      {CAMERA_ZED_URL !== '' && (
        <Box sx={{ background: palette.surface, border: `1px solid ${palette.surfaceBorder}`, borderRadius: 1, p: '14px 16px' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            <Typography sx={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: palette.textMuted }}>
              ZED Camera
            </Typography>
            {zed.live && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Box sx={{ width: 5, height: 5, borderRadius: '50%', background: palette.success, animation: 'blink 1.6s ease infinite' }} />
                <style>{'@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}'}</style>
                <Typography sx={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: palette.success }}>LIVE</Typography>
              </Box>
            )}
          </Box>
          <StreamBox frameUrl={zed.frameUrl} live={zed.live} error={zed.error} height={200} />
        </Box>
      )}

      <Box sx={{ background: palette.surface, border: `1px solid ${palette.surfaceBorder}`, borderRadius: 1, p: '14px 16px' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography sx={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: palette.textMuted }}>
            Camera Feed
          </Typography>
          {ext.live && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Box sx={{ width: 5, height: 5, borderRadius: '50%', background: palette.success, animation: 'blink 1.6s ease infinite' }} />
              <style>{'@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}'}</style>
              <Typography sx={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: palette.success }}>LIVE</Typography>
            </Box>
          )}
        </Box>
        <StreamBox
          frameUrl={ext.frameUrl}
          live={ext.live}
          error={ext.error}
          height={CAMERA_ZED_URL !== '' ? 200 : 300}
          fallback={!connected ? 'NO SIGNAL' : undefined}
        />
      </Box>
    </Box>
  );
}

function StreamBox({ frameUrl, live, error, height, fallback }: {
  frameUrl: string | null;
  live: boolean;
  error: boolean;
  height: number;
  fallback?: string;
}) {
  return (
    <Box sx={{ position: 'relative', height, background: palette.bg, borderRadius: '3px', border: `1px solid ${palette.surfaceBorder}`, overflow: 'hidden' }}>
      {frameUrl && (
        <img
          src={frameUrl}
          alt="Camera stream"
          style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
        />
      )}
      {(!live && !frameUrl) && (
        <Box sx={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
          <Typography sx={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: error ? palette.error : palette.textMuted }}>
            {fallback || (error ? 'STREAM ERROR' : 'CONNECTING...')}
          </Typography>
        </Box>
      )}
    </Box>
  );
}

export const VisionCamera = memo(VisionCameraInner);
