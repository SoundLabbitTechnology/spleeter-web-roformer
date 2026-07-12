import * as React from 'react';
import { Col, Form, ToggleButton, ToggleButtonGroup } from 'react-bootstrap';
import {
  DEFAULT_OUTPUT_FORMAT,
  DEFAULT_SEPARATION_MODE,
  LOSSLESS_OUTPUT_FORMATS,
  LOSSY_OUTPUT_FORMATS,
} from '../../../Constants';
import { SeparationMode, Separator } from '../../../models/Separator';

interface Props {
  className: string;
  handleModelChange: (newModel: string) => void;
  handleRandomShiftsChange: (newRandomShifts: number) => void;
  handleOutputFormatChange: (newOutputFormat: number) => void;
}

interface State {
  selectedMode: SeparationMode;
  output_format: number;
}

const MODE_MODELS: Record<SeparationMode, Separator> = {
  fast: 'htdemucs',
  quality: 'bs_roformer_6s',
  vocal: 'mel_roformer_vocals',
  efficient: 'scnet',
};

const MODE_DESCRIPTIONS: Record<SeparationMode, string> = {
  fast: 'Fast general-purpose separation into vocals, drums, bass, and other.',
  quality: 'Highest-quality six-stem separation with guitar and piano.',
  vocal: 'Vocal-specialist separation into vocals and accompaniment.',
  efficient: 'Efficient four-stem separation with SCNet. Best for CPU-oriented batches.',
};

/** Three task-oriented separation presets for new mixes. */
class SeparatorFormGroup extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      selectedMode: DEFAULT_SEPARATION_MODE,
      output_format: DEFAULT_OUTPUT_FORMAT,
    };
  }

  onModeChange = (mode: SeparationMode): void => {
    this.setState({ selectedMode: mode });
    this.props.handleModelChange(MODE_MODELS[mode]);
    // The fast Demucs preset intentionally disables equivariant random shifts.
    this.props.handleRandomShiftsChange(0);
  };

  onBitrateChange = (event: React.ChangeEvent<HTMLSelectElement>): void => {
    const parsedVal = parseInt(event.target.value);
    this.setState({ output_format: parsedVal });
    this.props.handleOutputFormatChange(parsedVal);
  };

  render(): JSX.Element {
    const { selectedMode, output_format: bitrate } = this.state;
    const { className } = this.props;

    return (
      <Form.Group className={className} controlId="separator">
        <Form.Group className="mb-1">
          <Form.Label>Separation mode:</Form.Label>
          <Form.Row>
            <Col>
              <ToggleButtonGroup
                type="radio"
                name="separation-mode"
                value={selectedMode}
                onChange={this.onModeChange}>
                <ToggleButton id="mode-fast" variant="outline-secondary" value="fast">
                  Fast Demucs
                </ToggleButton>
                <ToggleButton id="mode-quality" variant="outline-secondary" value="quality">
                  High-quality 6-stem
                </ToggleButton>
                <ToggleButton id="mode-vocal" variant="outline-secondary" value="vocal">
                  Vocal isolation
                </ToggleButton>
                <ToggleButton id="mode-efficient" variant="outline-secondary" value="efficient">
                  Efficient SCNet
                </ToggleButton>
              </ToggleButtonGroup>
              <Form.Text className="d-block mt-2" muted>
                {MODE_DESCRIPTIONS[selectedMode]}
              </Form.Text>
            </Col>
          </Form.Row>
        </Form.Group>
        <Form.Row className="mt-2">
          <Col xs={6}>
            <Form.Group className="mb-0" controlId="bitrate-group">
              <Form.Label id="bitrate">Format:</Form.Label>
              <Form.Row>
                <Col>
                  <Form.Control as="select" defaultValue={bitrate} onChange={this.onBitrateChange}>
                    <optgroup label="Lossy">
                      {LOSSY_OUTPUT_FORMATS.map((val) => (
                        <option key={val[1]} value={val[0]}>
                          MP3 {val[1]}
                        </option>
                      ))}
                    </optgroup>
                    <optgroup label="Lossless">
                      {LOSSLESS_OUTPUT_FORMATS.map((val) => (
                        <option key={val[1]} value={val[0]}>
                          {val[1]}
                        </option>
                      ))}
                    </optgroup>
                  </Form.Control>
                </Col>
              </Form.Row>
            </Form.Group>
          </Col>
        </Form.Row>
      </Form.Group>
    );
  }
}

export default SeparatorFormGroup;
