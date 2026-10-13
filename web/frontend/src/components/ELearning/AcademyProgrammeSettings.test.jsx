import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import i18n from '../../i18n';
import AcademyProgrammeSettings from './AcademyProgrammeSettings';
beforeEach(async()=>{await i18n.changeLanguage('en');});afterEach(cleanup);
it('shows only entitled programme configuration sections',()=>{
 render(<AcademyProgrammeSettings settings={{}} capabilities={{tuition:true}} update={vi.fn()}/>);
 expect(screen.getByRole('heading',{name:'Support Programme'})).toBeTruthy();expect(screen.getByRole('heading',{name:'Notifications'})).toBeTruthy();expect(screen.queryByRole('heading',{name:'Affiliates'})).toBeNull();expect(screen.queryByRole('heading',{name:'Withdrawals'})).toBeNull();expect(screen.queryByRole('heading',{name:'Exchange Programme'})).toBeNull();
});
it('preserves the existing withdrawal methods array contract while editing one method per line',()=>{
 const update=vi.fn();render(<AcademyProgrammeSettings settings={{withdrawal_methods:['Bank transfer','PayPal']}} capabilities={{withdrawal:true}} update={update}/>);const methods=screen.getByLabelText('Withdrawal methods (one per line)');expect(methods.value).toBe('Bank transfer\nPayPal');fireEvent.change(methods,{target:{value:'Bank transfer\nPayPal\n'}});expect(update).toHaveBeenCalledWith('withdrawal_methods',['Bank transfer','PayPal']);
});
it('defaults learning notifications on while preserving an explicit opt-out and links the existing web notification setup',()=>{
 const props={capabilities:{},update:vi.fn()};const {rerender}=render(<AcademyProgrammeSettings {...props} settings={{}}/>);
 expect(screen.getByRole('switch',{name:'Enable learning notifications'}).checked).toBe(true);
 expect(screen.getByRole('link',{name:'Manage web notifications'}).getAttribute('href')).toBe('/notifications');
 rerender(<AcademyProgrammeSettings {...props} settings={{learning_notifications_enabled:false}}/>);
 expect(screen.getByRole('switch',{name:'Enable learning notifications'}).checked).toBe(false);
});
