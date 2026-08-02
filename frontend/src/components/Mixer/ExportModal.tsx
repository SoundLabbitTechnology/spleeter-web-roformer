import * as React from 'react';
import { Alert, Button, Modal, ProgressBar } from 'react-bootstrap';
import { PartId } from '../../models/PartId';
import { ExportMode, StemPart } from '../../utils/stemExport';
import ExportForm from './ExportForm';
import './ExportModal.css';

export interface ExportSubmitParams {
  name: string;
  mode: ExportMode;
  selectedParts: PartId[];
}

interface Props {
  defaultName: string;
  availableParts: StemPart[];
  initialSelectedParts: PartId[];
  show: boolean;
  hide: () => void;
  submit: (params: ExportSubmitParams) => Promise<void>;
  isExporting: boolean;
  exportRatio: number;
  /** When true, mix mode uses mixer volume levels (Mixer). Otherwise equal volume. */
  volumeAware?: boolean;
}

interface State {
  mixName: string;
  mode: ExportMode;
  selectedParts: PartId[];
}

/**
 * Component for the export modal (custom mix or stems ZIP).
 */
class ExportModal extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      mixName: props.defaultName,
      mode: 'mix',
      selectedParts: [...props.initialSelectedParts],
    };
  }

  componentDidUpdate(prevProps: Props): void {
    if (!prevProps.show && this.props.show) {
      this.setState({
        mixName: this.props.defaultName,
        mode: 'mix',
        selectedParts: [...this.props.initialSelectedParts],
      });
    }
  }

  submit = async (): Promise<void> => {
    await this.props.submit({
      name: this.state.mixName,
      mode: this.state.mode,
      selectedParts: this.state.selectedParts,
    });
  };

  handleMixNameChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const name = e.currentTarget.value;
    this.setState({
      mixName: name && name !== '' ? name : this.props.defaultName,
    });
    e.stopPropagation();
  };

  handleModeChange = (mode: ExportMode): void => {
    this.setState({ mode });
  };

  handlePartToggle = (partId: PartId): void => {
    this.setState(prev => {
      const selected = prev.selectedParts.includes(partId)
        ? prev.selectedParts.filter(id => id !== partId)
        : [...prev.selectedParts, partId];
      return { selectedParts: selected };
    });
  };

  render(): JSX.Element | null {
    const { defaultName, availableParts, isExporting, exportRatio, volumeAware } = this.props;
    const { mixName, mode, selectedParts } = this.state;
    const exportPct = Math.round(exportRatio * 100);
    const canSubmit = selectedParts.length > 0 && !isExporting;

    const infoText =
      mode === 'zip'
        ? 'This downloads the selected parts as individual files in a ZIP archive.'
        : volumeAware
        ? 'This exports a custom mix using the current volume levels for the selected parts.'
        : 'This exports a custom mix of the selected parts at equal volume.';

    return (
      <Modal show={this.props.show} onHide={!isExporting ? this.props.hide : undefined}>
        <Modal.Header closeButton>
          <Modal.Title>Export</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Alert variant="info" className="mb-2">
            {infoText}
          </Alert>
          <ExportForm
            defaultName={defaultName}
            mixName={mixName}
            mode={mode}
            availableParts={availableParts}
            selectedParts={selectedParts}
            handleNameChange={this.handleMixNameChange}
            handleModeChange={this.handleModeChange}
            handlePartToggle={this.handlePartToggle}
          />
          <ProgressBar
            bsPrefix="export-progress"
            variant="success"
            now={exportPct}
            label={exportPct > 5 ? `${exportPct}%` : ''}
            animated={isExporting}
            min={0}
            max={100}
          />
        </Modal.Body>
        <Modal.Footer>
          <Button variant="success" onClick={this.submit} disabled={!canSubmit}>
            {isExporting ? 'Exporting...' : mode === 'zip' ? 'Download ZIP' : 'Export mix'}
          </Button>
        </Modal.Footer>
      </Modal>
    );
  }
}

export default ExportModal;
