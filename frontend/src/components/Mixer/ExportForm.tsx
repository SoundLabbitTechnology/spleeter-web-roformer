import * as React from 'react';
import { Col, Form } from 'react-bootstrap';
import { PartId } from '../../models/PartId';
import { ExportMode, StemPart } from '../../utils/stemExport';

interface Props {
  defaultName: string;
  mixName: string;
  mode: ExportMode;
  availableParts: StemPart[];
  selectedParts: PartId[];
  handleNameChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  handleModeChange: (mode: ExportMode) => void;
  handlePartToggle: (partId: PartId) => void;
}

/**
 * Dynamic mix export form with mode and part selection.
 */
class ExportForm extends React.Component<Props> {
  render(): JSX.Element {
    const {
      defaultName,
      handleNameChange,
      mode,
      availableParts,
      selectedParts,
      handleModeChange,
      handlePartToggle,
    } = this.props;

    return (
      <Form>
        <Form.Row>
          <Form.Group as={Col} controlId="export-mode">
            <Form.Label>Export as:</Form.Label>
            <div>
              <Form.Check
                inline
                type="radio"
                id="export-mode-mix"
                label="Custom mix (single file)"
                name="exportMode"
                checked={mode === 'mix'}
                onChange={() => handleModeChange('mix')}
              />
              <Form.Check
                inline
                type="radio"
                id="export-mode-zip"
                label="Selected stems (ZIP)"
                name="exportMode"
                checked={mode === 'zip'}
                onChange={() => handleModeChange('zip')}
              />
            </div>
          </Form.Group>
        </Form.Row>
        <Form.Row>
          <Form.Group as={Col} controlId="export-parts">
            <Form.Label>Parts to include:</Form.Label>
            <div>
              {availableParts.map(part => (
                <Form.Check
                  key={part.id}
                  inline
                  type="checkbox"
                  id={`export-part-${part.id}`}
                  label={part.label}
                  checked={selectedParts.includes(part.id)}
                  onChange={() => handlePartToggle(part.id)}
                />
              ))}
            </div>
          </Form.Group>
        </Form.Row>
        <Form.Row>
          <Form.Group as={Col} controlId="mix">
            <Form.Label>{mode === 'zip' ? 'ZIP name:' : 'Mix name:'}</Form.Label>
            <Form.Control
              name="mixName"
              defaultValue={defaultName}
              placeholder={defaultName}
              onChange={handleNameChange}
            />
          </Form.Group>
        </Form.Row>
      </Form>
    );
  }
}

export default ExportForm;
