import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import i18n from '../../i18n';
import LearningErrorNotice from './LearningErrorNotice';
beforeEach(async()=>{await i18n.changeLanguage('en');});afterEach(()=>{cleanup();vi.useRealTimers();});
it('shares one dismissible toast for concurrent errors while retaining contextual messages and retry',()=>{
 const retry=vi.fn();render(<><LearningErrorNotice><p>Unable to load courses.</p><button onClick={retry}>Try again</button></LearningErrorNotice><LearningErrorNotice>Unable to load labels.</LearningErrorNotice></>);
 expect(document.querySelectorAll('.ecommerce-toast')).toHaveLength(1);
 expect(screen.getAllByRole('alert')).toHaveLength(2);
 fireEvent.click(screen.getByRole('button',{name:'Dismiss notification'}));
 expect(document.querySelector('.ecommerce-toast')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Try again'}));expect(retry).toHaveBeenCalledOnce();
 expect(screen.getByText('Unable to load courses.')).toBeTruthy();
});
it('does not toast informational states and shows a new toast for a subsequent error',()=>{
 const {rerender}=render(<LearningErrorNotice role="status">Loading</LearningErrorNotice>);
 expect(document.querySelector('.ecommerce-toast')).toBeNull();
 rerender(<LearningErrorNotice>Unable to save.</LearningErrorNotice>);
 expect(document.querySelector('.ecommerce-toast')).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'Dismiss notification'}));
 rerender(<div/>);rerender(<LearningErrorNotice>Unable to save.</LearningErrorNotice>);
 expect(document.querySelector('.ecommerce-toast')).toBeTruthy();
});
it('uses Arabic toast copy and direction',async()=>{
 await i18n.changeLanguage('ar');render(<LearningErrorNotice>تعذر الحفظ</LearningErrorNotice>);
 expect(document.querySelector('.ecommerce-toast').getAttribute('dir')).toBe('rtl');
 expect(screen.getByText('حدث خطأ')).toBeTruthy();
});
