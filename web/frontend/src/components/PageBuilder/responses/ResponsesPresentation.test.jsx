import {cleanup,fireEvent,render,screen,within} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import ResponsesToolbar from './components/ResponsesToolbar';
import ResponsesDataBrowser from './components/ResponsesDataBrowser';
import {getResponsesContent} from '../../../content/pageBuilder/responsesContent';
afterEach(cleanup);
const t=getResponsesContent('en');
it('preserves Builder completed/incomplete controls and resume settings by default',()=>{
 const update=vi.fn();render(<ResponsesToolbar t={t} responseView="completed" setResponseView={update} data={{selectedForm:{id:'builder-form',title:'Builder form'},displayedResponses:[]}}/>);
 fireEvent.click(screen.getByRole('tab',{name:'Incomplete'}));expect(update).toHaveBeenCalledWith('incomplete');
 expect(screen.getByRole('tab',{name:'Completed'})).toBeTruthy();expect(screen.getByRole('button',{name:'Settings'})).toBeTruthy();
});
it('keeps Builder record controls while preserving zero-valued answer previews',()=>{
 const row={id:'record',answers:{number:0}};
 render(<ResponsesDataBrowser t={t} fields={[{id:'number',label:'Count'}]} displayedResponses={[row]} responses={[row]} selectedResponse={row} selectedOffset={0} setSelectedResponseId={()=>{}} formatSavedValue={value=>String(value)} />);
 expect(within(screen.getByRole('button',{name:/^#1/})).getByText('0',{selector:'strong'})).toBeTruthy();
 expect(screen.getByRole('button',{name:'Edit'})).toBeTruthy();expect(screen.getByRole('button',{name:'Delete'})).toBeTruthy();
});
