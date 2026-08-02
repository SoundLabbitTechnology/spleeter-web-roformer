import { createFFmpeg, FFmpeg } from '@jeffreyca/ffmpeg';
import * as React from 'react';
import { Alert, Badge, Button, OverlayTrigger, Tooltip } from 'react-bootstrap';
import { Download } from 'react-bootstrap-icons';
import BootstrapTable, { ColumnDescription, ColumnFormatter, SortOrder } from 'react-bootstrap-table-next';
import 'react-bootstrap-table-next/dist/react-bootstrap-table2.min.css';
import { OverlayInjectedProps } from 'react-bootstrap/esm/Overlay';
import { DEFAULT_OUTPUT_FORMAT } from '../../Constants';
import { DynamicMix } from '../../models/DynamicMix';
import { separatorLabelMap } from '../../models/Separator';
import { StaticMix } from '../../models/StaticMix';
import { toLocaleDateTimeString, toRelativeDateSpan } from '../../Utils';
import {
  exportSelectedMix,
  exportStemsZip,
  FFMPEG_CORE_PATH,
  getAvailableStems,
} from '../../utils/stemExport';
import { AccompBadge, AllBadge, BassBadge, DrumsBadge, GuitarBadge, PianoBadge, VocalsBadge } from '../Badges';
import ExportModal, { ExportSubmitParams } from '../Mixer/ExportModal';
import DeleteDynamicMixButton from './Button/DeleteDynamicMixButton';
import DeleteStaticMixButton from './Button/DeleteStaticMixButton';
import PausePlayButton from './Button/PausePlayButton';
import PlayMixButton from './Button/PlayMixButton';
import StatusIcon from './StatusIcon';
import './MixTable.css';

/**
 * Represents a dynamic or static mix.
 */
interface MixItem {
  id: string;
  static: boolean;
  mix: DynamicMix | StaticMix;
  date_created: string;
}

/**
 * Formatter function for status column
 */
const statusColFormatter: ColumnFormatter<MixItem> = (cell, row, rowIndex) => {
  let finishedDateTimeText = row.mix.date_finished
    ? `Done at ${toLocaleDateTimeString(row.mix.date_finished)}`
    : undefined;
  if (row.mix.error) {
    if (finishedDateTimeText) {
      finishedDateTimeText += '\n';
    }
    finishedDateTimeText += `Error: ${row.mix.error}`;
  }

  return (
    <div className="d-flex align-items-center justify-content-start">
      <StatusIcon status={row.mix.status} overlayText={finishedDateTimeText} />
    </div>
  );
};

/**
 * Formatter function for play/mix column
 */
const playColFormatter: ColumnFormatter<MixItem> = (cell, row, rowIndex, formatExtraData) => {
  if (row.static) {
    // Button acts as play/pause for static mixes
    const { currentSongUrl, isPlaying, onPauseClick, onPlayClick } = formatExtraData;
    const mix = row.mix as StaticMix;
    const isPlayingCurrent = isPlaying && currentSongUrl === mix.url;

    return (
      <div className="d-flex align-items-center justify-content-start">
        <PausePlayButton
          playing={isPlayingCurrent}
          disabled={!mix.url}
          disabledText="Processing"
          song={mix}
          onPauseClick={onPauseClick}
          onPlayClick={onPlayClick}
        />
      </div>
    );
  } else {
    // Button acts as link to mixer for dynamic mixes
    const mix = row.mix as DynamicMix;
    return (
      <div className="d-flex align-items-center justify-content-start">
        <PlayMixButton mixId={mix.id} />
      </div>
    );
  }
};

/**
 * Formatter function for model column.
 */
const modelFormatter: ColumnFormatter<MixItem> = (cellContent, row) => {
  const separator = row.mix.separator;
  const shouldShowTooltip = row.mix.extra_info.length > 0;

  const badge = (
    <Badge variant="dark" style={shouldShowTooltip ? { cursor: 'pointer' } : {}}>
      {separatorLabelMap[separator]}
    </Badge>
  );

  const renderTooltip = (props: OverlayInjectedProps) => {
    // Show tooltip of extra info separated by line breaks
    return (
      <Tooltip id="status-tooltip" {...props}>
        {row.mix.extra_info
          .map(item => <>{item}</>)
          .reduce((result, item) => (
            <>
              {result}
              <br />
              {item}
            </>
          ))}
      </Tooltip>
    );
  };

  return (
    <h5 className="mb-0">
      {shouldShowTooltip ? (
        <OverlayTrigger placement="right" delay={{ show: 50, hide: 50 }} overlay={renderTooltip}>
          {badge}
        </OverlayTrigger>
      ) : (
        badge
      )}
    </h5>
  );
};

/**
 * Formatter function for included parts column.
 */
const partsFormatter: ColumnFormatter<MixItem> = (cellContent, row) => {
  if (row.static) {
    // For static mixes, show included parts as separate badges
    const mix = row.mix as StaticMix;
    return (
      <h5 className="mb-0">
        {mix.vocals && <VocalsBadge />}
        {mix.other && <AccompBadge />}
        {mix.bass && <BassBadge />}
        {mix.drums && <DrumsBadge />}
        {mix.guitar && <GuitarBadge />}
        {mix.piano && <PianoBadge />}
      </h5>
    );
  } else {
    // For dynamic mixes, show single 'All' badge
    return (
      <h5 className="mb-0">
        <AllBadge />
      </h5>
    );
  }
};

/**
 * Formatter for download/delete column.
 */
const actionFormatter: ColumnFormatter<MixItem> = (cell, row, rowIndex, formatExtraData) => {
  const { onDeleteDynamicMixClick, onDeleteStaticMixClick, onExportDynamicMixClick } = formatExtraData;

  if (row.static) {
    const mix = row.mix as StaticMix;
    const { url } = mix;

    return (
      <div className="d-flex align-items-center justify-content-end">
        <Button variant="success" disabled={!url} href={url} target="_blank">
          <Download />
        </Button>
        <DeleteStaticMixButton onClick={onDeleteStaticMixClick} mix={mix} />
      </div>
    );
  } else {
    const mix = row.mix as DynamicMix;
    const canExport = mix.status === 'Done' && getAvailableStems(mix).length > 0;
    return (
      <div className="d-flex align-items-center justify-content-end">
        <Button
          variant="success"
          className="mr-1"
          disabled={!canExport}
          onClick={() => onExportDynamicMixClick(mix)}
          title="Export selected parts"
        >
          <Download />
        </Button>
        <DeleteDynamicMixButton onClick={onDeleteDynamicMixClick} mix={mix} />
      </div>
    );
  }
};

interface Props {
  dynamicMixes: DynamicMix[];
  staticMixes: StaticMix[];
  currentSongUrl?: string;
  isPlaying: boolean;
  onDeleteDynamicMixClick: (mix: DynamicMix) => void;
  onDeleteStaticMixClick: (mix: StaticMix) => void;
  onPauseClick: (song: StaticMix) => void;
  onPlayClick: (song: StaticMix) => void;
}

interface State {
  exportMix?: DynamicMix;
  showExportModal: boolean;
  isExporting: boolean;
  exportRatio: number;
  exportError?: string;
}

/**
 * Component for table showing all of a source track's dynamic and static mixes.
 */
class MixTable extends React.Component<Props, State> {
  ffmpeg?: FFmpeg;
  ffmpegLoading?: Promise<FFmpeg>;

  constructor(props: Props) {
    super(props);
    this.state = {
      showExportModal: false,
      isExporting: false,
      exportRatio: 0,
    };
  }

  componentWillUnmount(): void {
    try {
      this.ffmpeg?.exit();
    } catch (e) {
      // ignore
    }
  }

  ensureFfmpeg = async (): Promise<FFmpeg> => {
    if (this.ffmpeg) {
      return this.ffmpeg;
    }
    if (!this.ffmpegLoading) {
      this.ffmpegLoading = (async () => {
        const ffmpeg = createFFmpeg({
          corePath: FFMPEG_CORE_PATH,
          log: false,
          progress: ({ ratio }) => {
            this.setState({ exportRatio: Math.min(1, Math.max(0, ratio)) });
          },
        });
        await ffmpeg.load();
        this.ffmpeg = ffmpeg;
        return ffmpeg;
      })();
    }
    return this.ffmpegLoading;
  };

  onExportDynamicMixClick = (mix: DynamicMix): void => {
    this.setState({
      exportMix: mix,
      showExportModal: true,
      exportRatio: 0,
      exportError: undefined,
    });
  };

  onExportHide = (): void => {
    if (this.state.isExporting) {
      return;
    }
    this.setState({
      showExportModal: false,
      exportMix: undefined,
      exportRatio: 0,
    });
  };

  onExportSubmit = async (params: ExportSubmitParams): Promise<void> => {
    const { exportMix } = this.state;
    if (!exportMix) {
      return;
    }

    const available = getAvailableStems(exportMix);
    const selectedStems = available.filter(stem => params.selectedParts.includes(stem.id));
    if (selectedStems.length === 0) {
      this.setState({ exportError: 'Select at least one part.' });
      return;
    }

    this.setState({
      isExporting: true,
      exportRatio: 0,
      exportError: undefined,
    });

    try {
      if (params.mode === 'zip') {
        await exportStemsZip(
          selectedStems.map(s => ({ url: s.url, fileName: s.fileName })),
          params.name,
          ratio => this.setState({ exportRatio: ratio })
        );
      } else {
        const ffmpeg = await this.ensureFfmpeg();
        await exportSelectedMix(
          ffmpeg,
          selectedStems.map(stem => ({
            fileName: stem.fileName,
            url: stem.url,
            volumeDb: 0,
          })),
          params.name,
          exportMix.bitrate ?? DEFAULT_OUTPUT_FORMAT,
          ratio => this.setState({ exportRatio: ratio })
        );
      }
      this.setState({
        showExportModal: false,
        exportMix: undefined,
      });
    } catch (ex: any) {
      this.setState({
        exportError: ex?.message || 'Export failed.',
      });
      console.error(ex);
    } finally {
      this.setState({
        isExporting: false,
        exportRatio: 0,
      });
    }
  };

  render(): JSX.Element {
    const {
      staticMixes,
      dynamicMixes,
      currentSongUrl,
      isPlaying,
      onDeleteDynamicMixClick,
      onDeleteStaticMixClick,
      onPauseClick,
      onPlayClick,
    } = this.props;
    const { exportMix, showExportModal, isExporting, exportRatio, exportError } = this.state;

    const columns: ColumnDescription[] = [
      {
        dataField: 'status_dummy',
        isDummyField: true,
        text: '',
        formatter: statusColFormatter,
        headerStyle: () => {
          return { width: '40px', paddingLeft: '28px' };
        },
        style: () => {
          return { width: '40px', paddingLeft: '28px' };
        },
      },
      {
        dataField: 'url_dummy',
        isDummyField: true,
        text: '',
        formatter: playColFormatter,
        formatExtraData: {
          currentSongUrl: currentSongUrl,
          isPlaying: isPlaying,
          onPauseClick: onPauseClick,
          onPlayClick: onPlayClick,
        },
        sort: true,
        sortFunc: (_a: boolean, b: boolean, order: SortOrder, _dataField: unknown, rowA: MixItem, rowB: MixItem) => {
          // Custom sort function to sort based on static and dynamic mix types.
          if (rowA.static && !rowB.static) {
            return order === 'asc' ? 1 : -1;
          } else if (!rowA.static && rowB.static) {
            return order === 'asc' ? -1 : 1;
          }
          return 0;
        },
        headerStyle: () => {
          return { width: '65px' };
        },
      },
      {
        dataField: 'separator_dummy',
        isDummyField: true,
        text: 'Model',
        formatter: modelFormatter,
        sort: true,
        sortFunc: (a: string, b: string, order: SortOrder, _dataField: unknown, rowA: MixItem, rowB: MixItem) => {
          a = rowA.mix.separator;
          b = rowB.mix.separator;

          if (order === 'asc') {
            return a.localeCompare(b);
          } else {
            return b.localeCompare(a);
          }
        },
        style: () => {
          return { width: '200px' };
        },
        headerStyle: () => {
          return { width: '200px' };
        },
      },
      {
        dataField: 'parts',
        isDummyField: true,
        text: 'Included parts',
        formatter: partsFormatter,
        style: () => {
          return { minWidth: '300px' };
        },
      },
      {
        dataField: 'date_created',
        text: 'Created',
        formatter: toRelativeDateSpan,
        sort: true,
      },
      {
        dataField: 'file',
        text: '',
        formatter: actionFormatter,
        formatExtraData: {
          onDeleteDynamicMixClick: onDeleteDynamicMixClick,
          onDeleteStaticMixClick: onDeleteStaticMixClick,
          onExportDynamicMixClick: this.onExportDynamicMixClick,
        },
        style: () => {
          return { maxWidth: '160px', paddingRight: 28 };
        },
      },
    ];

    const defaultSort = { dataField: 'date_created', order: 'desc' as SortOrder };

    // Merge static and dynamic mixes into single list
    let data: MixItem[] = [];

    data = data.concat(
      staticMixes.map(mix => {
        return {
          id: mix.id,
          static: true,
          mix: mix,
          date_created: mix.date_created,
          date_finished: mix.date_finished,
        } as MixItem;
      })
    );

    data = data.concat(
      dynamicMixes.map(mix => {
        return {
          id: mix.id,
          static: false,
          mix: mix,
          date_created: mix.date_created,
          date_finished: mix.date_finished,
        } as MixItem;
      })
    );

    const availableParts = exportMix ? getAvailableStems(exportMix) : [];

    if (data.length > 0) {
      return (
        <div className="inner-table-div">
          {exportError && (
            <Alert variant="danger" className="mb-2" onClose={() => this.setState({ exportError: undefined })} dismissible>
              {exportError}
            </Alert>
          )}
          <BootstrapTable
            classes="inner-table mb-0"
            bootstrap4
            keyField="id"
            data={data}
            columns={columns}
            defaultSorted={[defaultSort]}
            defaultSortDirection="asc"
            bordered={false}
          />
          <ExportModal
            defaultName={exportMix ? `${exportMix.title} - ${exportMix.artist}` : 'export'}
            availableParts={availableParts}
            initialSelectedParts={availableParts.map(p => p.id)}
            show={showExportModal}
            hide={this.onExportHide}
            submit={this.onExportSubmit}
            isExporting={isExporting}
            exportRatio={exportRatio}
            volumeAware={false}
          />
        </div>
      );
    } else {
      return (
        <div className="m-4 text-center">
          <p>No mixes. Click &ldquo;Dynamic Mix&rdquo; or &ldquo;Static Mix&rdquo; to create one.</p>
        </div>
      );
    }
  }
}

export default MixTable;
