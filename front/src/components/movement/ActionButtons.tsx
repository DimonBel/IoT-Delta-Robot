import { memo } from 'react';
import { Button, Box } from '@mui/material';

interface ActionButtonsProps {
  onIsDelta: () => void;
  onGetPosition: () => void;
  onHome: () => void;
  disabled?: boolean;
}

function ActionButtonsInner({ onIsDelta, onGetPosition, onHome, disabled = false }: ActionButtonsProps) {
  return (
    <Box sx={{ display: 'flex', gap: '4px' }}>
      <Button onClick={onIsDelta} disabled={disabled} variant="outlined" size="small" sx={{ fontSize: 11 }}>
        IsDelta
      </Button>
      <Button onClick={onGetPosition} disabled={disabled} variant="outlined" size="small" sx={{ fontSize: 11 }}>
        Get Pos
      </Button>
      <Button onClick={onHome} disabled={disabled} variant="outlined" size="small" sx={{ fontSize: 11 }}>
        Home
      </Button>
    </Box>
  );
}

export const ActionButtons = memo(ActionButtonsInner);
