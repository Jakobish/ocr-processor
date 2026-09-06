import {test,expect} from '@playwright/test';
test('unconfigured identity shows an honest integration state',async({page})=>{
 await page.goto('/');
 await expect(page.getByRole('heading',{name:'חיבור מערכת ההזדהות'})).toBeVisible();
 await expect(page.locator('html')).toHaveAttribute('dir','rtl');
 await expect(page.getByText('בחירת ה־starter')).toBeVisible();
});
