import { Box } from '@mui/material';
import { palette } from '../../theme';

interface NavigationTabsProps {
  currentPath: string;
  onNavigate: (path: string) => void;
}

const NAV_ITEMS = [
  { label: 'Overview', path: '/' },
  { label: 'Control', path: '/control' },
  { label: 'Jog', path: '/movement' },
  { label: 'Grid', path: '/grid' },
];

export function NavigationTabs({ currentPath, onNavigate }: NavigationTabsProps) {
  return (
    <Box sx={{ display: 'flex', gap: 0 }}>
      {NAV_ITEMS.map((item) => {
        const active = currentPath === item.path;
        return (
          <Box
            key={item.label}
            onClick={() => onNavigate(item.path)}
            sx={{
              px: 2,
              py: '6px',
              cursor: 'pointer',
              position: 'relative',
              color: active ? palette.text : palette.textSecondary,
              fontWeight: active ? 500 : 400,
              fontSize: 13,
              transition: 'color 0.12s',
              '&:hover': {
                color: palette.text,
              },
              '&:after': active
                ? {
                    content: '""',
                    position: 'absolute',
                    bottom: -6,
                    left: 0,
                    right: 0,
                    height: 2,
                    background: palette.accent,
                    borderRadius: '1px 1px 0 0',
                  }
                : {},
            }}
          >
            {item.label}
          </Box>
        );
      })}
    </Box>
  );
}
